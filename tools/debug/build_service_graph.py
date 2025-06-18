#!/usr/bin/env python3
import ast
import json
import os
import re
import importlib.util
from collections import defaultdict

# Path to the process_config.py file relative to the openpilot root
PROCESS_CONFIG_PATH = "system/manager/process_config.py"
# Output file for the service graph
GRAPH_OUTPUT_FILE = "tools/debug/service_graph.json"
# openpilot root directory (assuming this script is in tools/debug/)
OPENPILOT_ROOT = os.path.join(os.path.dirname(__file__), "../..")

# -----------------------------------------------------------------------------
# Manual mapping for NativeProcess / DaemonProcess publishers
# -----------------------------------------------------------------------------
# Native binaries are written in C/C++ and are not amenable to quick AST parsing
# in this helper script.  We therefore maintain a *minimal* curated list that
# maps native process names -> list of services they are known to publish. This
# list is based on direct scans of the C++ sources (PubMaster(...) and send())
# and on the canonical SERVICE_LIST.  Update it whenever you add/change a native
# publisher.

MANUAL_NATIVE_PUBS = {
    # system/camerad
    "camerad": [
        "roadCameraState", "wideRoadCameraState", "driverCameraState", "thumbnail",
        "roadEncodeData", "wideRoadEncodeData", "driverEncodeData",
        "roadEncodeIdx", "wideRoadEncodeIdx", "driverEncodeIdx",
    ],

    # system/sensord
    "sensord": [
        "sensorEvents", "gyroscope", "gyroscope2", "accelerometer", "accelerometer2",
        "magnetometer", "lightSensor",
        "temperatureSensor", "temperatureSensor2",
    ],

    # selfdrive/modeld (C++)
    "modeld": ["modelV2", "drivingModelData"],

    # system/loggerd/encoderd variants
    "encoderd": [
        "roadEncodeIdx", "driverEncodeIdx", "wideRoadEncodeIdx",
        "roadEncodeData", "driverEncodeData", "wideRoadEncodeData",
        "qRoadEncodeIdx", "qRoadEncodeData",
    ],
    "stream_encoderd": [
        "livestreamRoadEncodeIdx", "livestreamWideRoadEncodeIdx", "livestreamDriverEncodeIdx",
        "livestreamRoadEncodeData", "livestreamWideRoadEncodeData", "livestreamDriverEncodeData",
    ],

    # selfdrive/locationd (native part)
    "locationd": ["liveLocationKalman", "gpsLocationExternal", "ubloxGnss", "gpsLocation"],

    # system/ubloxd
    "ubloxd": ["ubloxRaw", "ubloxGnss"],

    # system/mapsd (old qt map viewer)
    "mapsd": ["thumbnail"],

    # Native bridge tester
    "bridge": [],
}

def get_process_config():
    """Loads the procs list from system.manager.process_config"""
    config_abs_path = os.path.join(OPENPILOT_ROOT, PROCESS_CONFIG_PATH)
    spec = importlib.util.spec_from_file_location("process_config", config_abs_path)
    if spec is None or spec.loader is None:
        print(f"Error: Could not load process_config.py from {config_abs_path}")
        return []
    process_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(process_config)
    return getattr(process_config, 'procs', [])

class ServiceParser(ast.NodeVisitor):
    def __init__(self):
        self.subscribes = set()
        self.publishes = set()
        self.pubmaster_vars = set()

    def visit_Assign(self, node):
        # Track variable assignments to PubMaster instances
        # e.g., pm = messaging.PubMaster(['service1'])
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            if node.value.func.attr == 'PubMaster' and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == 'messaging':
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.pubmaster_vars.add(target.id)
                if len(node.value.args) > 0 and isinstance(node.value.args[0], (ast.List, ast.Set, ast.Tuple)):
                    for elt in node.value.args[0].elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            self.publishes.add(elt.value)
                        elif isinstance(elt, ast.Str): # Python < 3.8
                            self.publishes.add(elt.s)
        elif isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name): # For direct calls like pm = PubMaster(...)
             if node.value.func.id == 'PubMaster':
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.pubmaster_vars.add(target.id)
                if len(node.value.args) > 0 and isinstance(node.value.args[0], (ast.List, ast.Set, ast.Tuple)):
                    for elt in node.value.args[0].elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            self.publishes.add(elt.value)
                        elif isinstance(elt, ast.Str):
                             self.publishes.add(elt.s)
        self.generic_visit(node)

    def visit_Call(self, node):
        # messaging.SubMaster(['service1', 'service2'])
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == 'SubMaster' and isinstance(node.func.value, ast.Name) and node.func.value.id == 'messaging':
                if len(node.args) > 0 and isinstance(node.args[0], (ast.List, ast.Set, ast.Tuple)):
                    for elt in node.args[0].elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            self.subscribes.add(elt.value)
                        elif isinstance(elt, ast.Str): # Python < 3.8
                            self.subscribes.add(elt.s)
            # pm.send('service_name', data)
            elif node.func.attr == 'send' and isinstance(node.func.value, ast.Name) and node.func.value.id in self.pubmaster_vars:
                if len(node.args) > 0 and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    self.publishes.add(node.args[0].value)
                elif len(node.args) > 0 and isinstance(node.args[0], ast.Str): # Python < 3.8
                     self.publishes.add(node.args[0].s)

        # For direct calls like SubMaster(...)
        elif isinstance(node.func, ast.Name):
            if node.func.id == 'SubMaster':
                if len(node.args) > 0 and isinstance(node.args[0], (ast.List, ast.Set, ast.Tuple)):
                    for elt in node.args[0].elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            self.subscribes.add(elt.value)
                        elif isinstance(elt, ast.Str):
                            self.subscribes.add(elt.s)
        self.generic_visit(node)

def parse_file_services(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    tree = ast.parse(content, filename=filepath)
    parser = ServiceParser()
    parser.visit(tree)
    return parser.publishes, parser.subscribes

def main():
    print(f"Starting service graph generation. Root: {OPENPILOT_ROOT}")
    service_graph = defaultdict(lambda: {"publishes": set(), "subscribes": set()})
    procs = get_process_config()

    if not procs:
        print("No processes found. Exiting.")
        return

    print(f"Found {len(procs)} processes in process_config.py")

    for proc in procs:
        proc_name = proc.name
        # We are primarily interested in PythonProcess for AST parsing
        # NativeProcess service usage would require different (more complex) parsing
        # Get the class name of the process object to determine its type
        process_class_name = proc.__class__.__name__

        if process_class_name != "PythonProcess":
            # For NativeProcess, DaemonProcess etc., we might have a list of assumed publications
            # or we can try to infer them from SERVICE_LIST and process name conventions,
            # but this is less reliable. For now, we'll skip detailed parsing.
            # print(f"Skipping non-PythonProcess: {proc_name} (type: {process_class_name})")
            continue

        # proc.module for PythonProcess is like "selfdrive.controls.controlsd"
        # We need to convert this to a file path e.g. selfdrive/controls/controlsd.py
        module_path_as_file = proc.module.replace('.', '/') + ".py"
        py_filepath = os.path.join(OPENPILOT_ROOT, module_path_as_file)

        if os.path.exists(py_filepath):
            print(f"Parsing Python process: {proc_name} ({module_path_as_file})")
            try:
                publishes, subscribes = parse_file_services(py_filepath)
                service_graph[proc_name]["publishes"].update(publishes)
                service_graph[proc_name]["subscribes"].update(subscribes)
            except Exception as e:
                print(f"  Error parsing {py_filepath}: {e}")
        else:
            print(f"  Python file not found for {proc_name}: {py_filepath}")

    # ---------------------------------------------------------------------
    # Add manual native publisher mappings
    # ---------------------------------------------------------------------
    for proc in procs:
        proc_name = proc.name
        process_class_name = proc.__class__.__name__
        if process_class_name in ("NativeProcess", "DaemonProcess"):
            if proc_name in MANUAL_NATIVE_PUBS:
                service_graph[proc_name]["publishes"].update(MANUAL_NATIVE_PUBS[proc_name])
            else:
                # If we don't have a manual entry, at least create an empty stub
                if proc_name not in service_graph:
                    service_graph[proc_name]  # triggers default lambda

    # Convert sets to lists for JSON serialization
    final_graph = {
        proc: {
            "publishes": sorted(list(data["publishes"])),
            "subscribes": sorted(list(data["subscribes"]))
        }
        for proc, data in service_graph.items()
        if data["publishes"] or data["subscribes"] # Only include procs that have some service interaction
    }

    output_abs_path = os.path.normpath(os.path.join(OPENPILOT_ROOT, GRAPH_OUTPUT_FILE))
    print(f"Service graph generation complete. Saving to: {output_abs_path}")
    try:
        os.makedirs(os.path.dirname(output_abs_path), exist_ok=True)
        with open(output_abs_path, 'w') as f:
            json.dump(final_graph, f, indent=2)
        print("Successfully saved service graph.")
    except Exception as e:
        print(f"Error saving graph to {output_abs_path}: {e}")

if __name__ == "__main__":
    main()