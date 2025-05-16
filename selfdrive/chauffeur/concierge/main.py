#!/usr/bin/env python3
"""
Launch with:
    python -m selfdrive.chauffeur.concierge.main --dev      (auto-reload)
or
    uvicorn selfdrive.chauffeur.concierge.main:app --host 0.0.0.0 --port 5055
"""

import asyncio
import json
import os
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Any
from contextlib import asynccontextmanager
import datetime
import subprocess
from pydantic import BaseModel # For request body validation
import shlex # For parsing cd command arguments safely
import zmq # ADDED ZMQ IMPORT
import zmq.asyncio # <- make the Context class visible
import re # For parsing capnp files
import sys # Added to access the current Python interpreter

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from cereal import messaging  # already on the device

# Set CRASH_LOGS_DIR to the actual path on the device
CRASH_LOGS_DIR = Path("/data/crashes")

# Path to openpilot root, assuming main.py is in selfdrive/chauffeur/concierge
OPENPILOT_ROOT_PATH = Path(__file__).resolve().parent.parent.parent.parent
CEREAL_PATH = OPENPILOT_ROOT_PATH / "cereal"
LOG_CAPNP_PATH = CEREAL_PATH / "log.capnp"

BASE = Path(__file__).resolve().parent
templates = Environment(
    loader=FileSystemLoader(BASE / "templates"),
    autoescape=select_autoescape()
)

# background task: poll SubMaster every N ms and keep latest snapshot in RAM
STATUS = {}
POLLER_TASK = None

WANTED = ["deviceState", "carState", "thermal", "liveLocationKalman"]
available = [s for s in WANTED if s in messaging.SERVICE_LIST]

async def _status_poller() -> None:
    sm = messaging.SubMaster(available)
    try:
        while True:
            sm.update(0)
            snapshot = {"time": sm.frame}
            if "deviceState" in available:
                snapshot["deviceState"] = sm["deviceState"].to_dict()
            if "carState" in available:
                snapshot["carState"] = sm["carState"].to_dict()
            if "thermal" in available:
                snapshot["thermal"] = sm["thermal"].to_dict()
            if "liveLocationKalman" in available:
                snapshot["liveLocationKalman"] = sm["liveLocationKalman"].to_dict()
            STATUS.update(snapshot)
            await asyncio.sleep(0.25)
    except asyncio.CancelledError:
        print("Status poller cancelled.")
    except Exception as e:
        print(f"Error in status poller: {e}")


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    global POLLER_TASK
    print("Concierge starting up...")
    POLLER_TASK = asyncio.create_task(_status_poller())
    yield
    print("Concierge shutting down...")
    if POLLER_TASK:
        POLLER_TASK.cancel()
        try:
            await POLLER_TASK
        except asyncio.CancelledError:
            print("Poller task successfully cancelled on shutdown.")

# ZMQ context for mapd logs subscriber - can be global for the app instance
# It's better to create one context per application. FastAPI lifespan can manage this for production,
# but for a single subscriber, a module-level context is often acceptable.
_mapd_log_zmq_context = None
_service_monitor_process: asyncio.subprocess.Process | None = None
_service_monitor_active_services: List[str] = []

def get_mapd_log_zmq_context():
    global _mapd_log_zmq_context
    if _mapd_log_zmq_context is None:
        _mapd_log_zmq_context = zmq.asyncio.Context() # Use asyncio context for FastAPI
    return _mapd_log_zmq_context

# ──────────────────── FastAPI app ──────────────────────
app = FastAPI(title="Concierge", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

# routes
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    tmpl = templates.get_template("index.html")
    # For the main page, page_title_text is empty as base.html already has "The Concierge"
    # browser_title_suffix can be empty or specific like "Dashboard"
    return tmpl.render(request=request, browser_title_suffix="- Dashboard", page_title_text="")


@app.get("/api/status")
async def api_status() -> dict:
    return STATUS


@app.get("/stream/sse")
async def stream_status() -> StreamingResponse:
    async def event_source() -> AsyncGenerator[str, None]:
        last_frame = -1
        while True:
            frame = STATUS.get("time", -1)
            if frame != last_frame:
                last_frame = frame
                yield f"data: {json.dumps(STATUS)}\n\n"
            await asyncio.sleep(0.25)
    return StreamingResponse(event_source(), media_type="text/event-stream")


# Basic placeholder pages for our tiles
@app.get("/navigation", response_class=HTMLResponse)
async def navigation_page(request: Request):
    tmpl = templates.get_template("navigation.html")
    return tmpl.render(request=request, browser_title_suffix="- Navigation", page_title_text="- Navigation")

@app.get("/diagnostics", response_class=HTMLResponse)
async def diagnostics_page(request: Request):
    tmpl = templates.get_template("diagnostics.html")
    return tmpl.render(request=request, browser_title_suffix="- Diagnostics", page_title_text="- Diagnostics")

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    # tmpl = templates.get_template("logs.html")
    # return tmpl.render(request=request, browser_title_suffix="- Logs", page_title_text="- Logs")
    return "<h1>Logs Page</h1><p>Under Construction</p><a href='/'>Back to Dashboard</a>"

@app.get("/drive-data", response_class=HTMLResponse)
async def drive_data_page(request: Request):
    # tmpl = templates.get_template("drive_data.html")
    # return tmpl.render(request=request, browser_title_suffix="- Drive Data", page_title_text="- Drive Data")
    return "<h1>Drive Data Page</h1><p>Under Construction</p><a href='/'>Back to Dashboard</a>"

@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    # tmpl = templates.get_template("test.html")
    # return tmpl.render(request=request, browser_title_suffix="- Test", page_title_text="- Test")
    return "<h1>Test Page</h1><p>Under Construction</p><a href='/'>Back to Dashboard</a>"

@app.get("/api/monitorable-services")
async def api_monitorable_services_endpoint() -> Dict[str, List[str]]:
    return parse_capnp_services()

class StartMonitoringRequest(BaseModel):
    services: List[str]

@app.post("/api/start-service-monitoring")
async def start_service_monitoring_endpoint(payload: StartMonitoringRequest):
    global _service_monitor_process, _service_monitor_active_services
    services = payload.services
    if _service_monitor_process and _service_monitor_process.returncode is None:
        raise HTTPException(status_code=400, detail="Monitoring is already in progress.")
    if not services:
        raise HTTPException(status_code=400, detail="No services selected for monitoring.")

    _service_monitor_active_services = services
    # Build absolute path to the monitor script and invoke it with the current Python interpreter. Using
    # sys.executable avoids relying on executable bits being set on the script file.
    script_path = str(OPENPILOT_ROOT_PATH / "tools" / "debug" / "monitor_service.py")
    command = [sys.executable, "-u", script_path] + services + ["-r", "0.25", "-d", "0"]  # -u for unbuffered output so SSE is timely

    print(f"[MONITOR_START] Attempting to run command: {' '.join(command)} from CWD: {OPENPILOT_ROOT_PATH}")

    try:
        _service_monitor_process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=OPENPILOT_ROOT_PATH # Explicitly set CWD to openpilot root
        )
        print(f"[MONITOR_START] Subprocess started with PID: {_service_monitor_process.pid}")
        # Give a brief moment for the process to start or fail early
        await asyncio.sleep(0.1)
        if _service_monitor_process.returncode is not None: # Process exited immediately
            stderr_output = b""
            if _service_monitor_process.stderr:
                 stderr_output = await _service_monitor_process.stderr.read()
            _service_monitor_process = None # Clear the process
            _service_monitor_active_services = []
            error_detail = f"Failed to start monitoring script. Exit code: {_service_monitor_process.returncode}. Stderr: {stderr_output.decode('utf-8', errors='ignore')}"
            print(f"[MONITOR_START_FAIL] {error_detail}")
            raise HTTPException(status_code=500, detail=error_detail)

    except FileNotFoundError:
        _service_monitor_process = None
        _service_monitor_active_services = []
        error_detail = f"Error: The monitoring script '{script_path}' was not found. CWD: {OPENPILOT_ROOT_PATH}"
        print(f"[MONITOR_START_FAIL] {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)
    except Exception as e:
        _service_monitor_process = None
        _service_monitor_active_services = []
        error_detail = f"An unexpected error occurred while trying to start the monitoring script: {str(e)}"
        print(f"[MONITOR_START_FAIL] {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)

    return {"message": f"Started monitoring services: {', '.join(services)}"}

@app.get("/stream/service-monitoring")
async def stream_service_monitoring_sse() -> StreamingResponse:
    global _service_monitor_process, _service_monitor_active_services

    async def event_generator():
        if not _service_monitor_process or not _service_monitor_process.stdout:
            yield f"event: error\ndata: {json.dumps({'message': 'Monitoring process not started or stdout not available.'})}\n\n"
            print("[MONITOR_STREAM_ERROR] Process not started for SSE.")
            return

        print("[MONITOR_STREAM] SSE Stream started.")
        try:
            while True:
                if _service_monitor_process.stdout:
                    try:
                        line_bytes = await asyncio.wait_for(_service_monitor_process.stdout.readline(), timeout=1.0)
                    except asyncio.TimeoutError:
                        # Timeout reading line, check if process is still alive
                        if _service_monitor_process.returncode is not None:
                            print("[MONITOR_STREAM] Process ended (timeout on readline).")
                            break
                        yield ": keepalive\\n\\n" # Send keepalive if process is running but no output
                        continue

                    if not line_bytes: # EOF
                        if _service_monitor_process.returncode is not None:
                            print("[MONITOR_STREAM] Process ended (EOF on readline).")
                            break
                        await asyncio.sleep(0.1)
                        continue

                    line = line_bytes.decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue

                    parsed_data = {}
                    service_entries = line.split('\t')
                    for entry in service_entries:
                        parts = entry.strip().split('|')
                        if len(parts) == 4:
                            service_name = parts[0].strip()
                            try:
                                freq_str = parts[1].strip().replace(" Hz", "")
                                freq = float(freq_str) if freq_str != "-.-" else -1.0 # Handle placeholder for no data
                                valid = "valid=True" in parts[2]
                                alive = "alive=True" in parts[3]
                                parsed_data[service_name] = {"freq": freq, "valid": valid, "alive": alive, "raw": entry.strip()}
                            except ValueError:
                                print(f"[MONITOR_STREAM_PARSE_ERROR] Value error parsing for {service_name} from '{parts[1].strip()}' in '{entry}'")
                                parsed_data[service_name] = {"error": "parse_value_error", "raw": entry.strip()}
                            except IndexError:
                                print(f"[MONITOR_STREAM_PARSE_ERROR] Index error parsing '{entry}'")
                                # Attempt to find service name if possible
                                for s_name_active in _service_monitor_active_services:
                                    if s_name_active in entry:
                                        parsed_data[s_name_active] = {"error": "parse_index_error", "raw": entry.strip()}
                                        break
                        elif entry: # Non-empty entry that doesn't match format
                             # Try to associate with an active service if possible
                            found_service_for_malformed = False
                            for s_name_active in _service_monitor_active_services:
                                if s_name_active in entry:
                                     parsed_data[s_name_active] = {"status": "malformed", "raw": entry.strip()}
                                     found_service_for_malformed = True
                                     break
                            if not found_service_for_malformed:
                                if "unknown_entries" not in parsed_data: parsed_data["unknown_entries"] = []
                                parsed_data["unknown_entries"].append(entry.strip())


                    if parsed_data: # Only yield if we have something to send
                        yield f"data: {json.dumps(parsed_data)}\n\n"

                if _service_monitor_process.returncode is not None: # Process ended
                    print(f"[MONITOR_STREAM] Monitoring process ended with code: {_service_monitor_process.returncode}")
                    break
                # await asyncio.sleep(0.01) # Removed to rely on readline timeout or data availability

            # Check for stderr after process loop
            if _service_monitor_process and _service_monitor_process.stderr:
                stderr_bytes = await _service_monitor_process.stderr.read()
                stderr_output = stderr_bytes.decode('utf-8', errors='ignore').strip()
                if stderr_output:
                    print(f"[MONITOR_STREAM_STDERR] {stderr_output}")
                    yield f"event: error\ndata: {json.dumps({'message': 'Monitoring process stderr', 'detail': stderr_output})}\n\n"

            yield f"event: close\ndata: {json.dumps({'message': 'Monitoring stream ended.'})}\n\n"

        except asyncio.CancelledError:
            print("[MONITOR_STREAM] SSE Stream cancelled by client.")
            # Important: If client disconnects, try to stop the backend script
            await stop_service_monitoring_endpoint_route() # Call the stop function
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            print(f"[MONITOR_STREAM_ERROR] General error in service monitoring stream: {e}\n{tb_str}")
            yield f"event: error\ndata: {json.dumps({'message': 'Stream error', 'detail': str(e)})}\n\n"
        finally:
            print("[MONITOR_STREAM] SSE Stream generator finished.")
            # If the process is still running when the stream naturally ends (e.g. client didn't explicitly stop via button but closed tab)
            # we should also stop it. This is somewhat redundant with CancelledError handling but safer.
            if _service_monitor_process and _service_monitor_process.returncode is None:
                print("[MONITOR_STREAM] Stream ended, ensuring process is stopped.")
                await stop_service_monitoring_endpoint_route()


    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/stop-service-monitoring")
async def stop_service_monitoring_endpoint_route(): # Renamed to avoid conflict with internal call
    global _service_monitor_process, _service_monitor_active_services
    if _service_monitor_process and _service_monitor_process.returncode is None:
        try:
            print(f"[MONITOR_STOP] Attempting to terminate PID: {_service_monitor_process.pid}")
            _service_monitor_process.terminate()
            # Wait for a short period for the process to terminate.
            # A more robust solution might involve SIGKILL after a timeout if terminate isn't effective.
            await asyncio.wait_for(_service_monitor_process.wait(), timeout=5.0)
            print(f"[MONITOR_STOP] Terminated service monitoring process PID: {_service_monitor_process.pid}. Exit code: {_service_monitor_process.returncode}")
        except asyncio.TimeoutError:
            print(f"[MONITOR_STOP_WARN] Timeout waiting for process {_service_monitor_process.pid} to terminate. Sending SIGKILL.")
            _service_monitor_process.kill()
            await _service_monitor_process.wait()
            print(f"[MONITOR_STOP] Killed service monitoring process PID: {_service_monitor_process.pid}. Exit code: {_service_monitor_process.returncode}")
        except ProcessLookupError:
            print(f"[MONITOR_STOP] Process {_service_monitor_process.pid if _service_monitor_process else 'Unknown'} already terminated (ProcessLookupError).")
        except Exception as e:
            print(f"[MONITOR_STOP_ERROR] Error terminating process: {e}")
        finally: # Ensure globals are reset
            _service_monitor_process = None
            _service_monitor_active_services = []
        return {"message": "Service monitoring stopped."}

    # Reset globals even if process was already stopped or not found
    _service_monitor_process = None
    _service_monitor_active_services = []
    return {"message": "No active service monitoring process to stop or already stopped."}

@app.get("/mapd_logs_stream")
async def mapd_logs_sse_stream() -> StreamingResponse:
    print("[MAPD_STREAM_SETUP] Entered mapd_logs_sse_stream function.")
    async def log_event_source() -> AsyncGenerator[str, None]:
        socket = None # Initialize for finally block
        poller = None # Initialize for finally block
        connection_active = True
        try:
            print("[MAPD_STREAM_SETUP] log_event_source started.")
            context = get_mapd_log_zmq_context()
            print(f"[MAPD_STREAM_SETUP] Got ZMQ context: {type(context)}")

            socket = context.socket(zmq.SUB)
            print(f"[MAPD_STREAM_SETUP] Created ZMQ SUB socket: {type(socket)}")

            # Set linger to 0 before connect for SUB sockets that should close fast on error/shutdown
            socket.setsockopt(zmq.LINGER, 0)
            print("[MAPD_STREAM_SETUP] Set LINGER to 0 on ZMQ socket.")

            print("[MAPD_STREAM_SETUP] Attempting to connect to tcp://localhost:8607...")
            socket.connect("tcp://localhost:8607")
            print("[MAPD_STREAM_SETUP] Successfully called connect() on ZMQ socket.")

            print("[MAPD_STREAM_SETUP] Attempting to subscribe to all messages...")
            socket.subscribe("")
            print("[MAPD_STREAM_SETUP] Successfully subscribed to ZMQ socket.")

            poller = zmq.asyncio.Poller()
            poller.register(socket, zmq.POLLIN)
            print("[MAPD_STREAM_SETUP] ZMQ poller registered. Entering main loop...")

            while connection_active:
                events = await poller.poll(timeout=1000) # Poll with a timeout
                if socket in dict(events):
                    message = await socket.recv_string()
                    # print(f"[MAPD_STREAM_DATA] Received ZMQ: {message[:100]}...") # Uncomment for verbose data logging
                    yield f"data: {message}\\n\\n"
                else:
                    # print("[MAPD_STREAM_KEEPALIVE] Sending keep-alive.") # Uncomment for verbose keep-alive logging
                    yield ": keepalive\\n\\n"
        except asyncio.CancelledError:
            print("[MAPD_STREAM_CANCELLED] MapD log stream cancelled by client disconnect or server shutdown.")
            connection_active = False
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            print(f"[MAPD_STREAM_ERROR] Error in MapD log stream: {type(e).__name__}: {e}\\nTraceback:\\n{tb_str}")
            connection_active = False
            # Consider yielding a specific error to client if stream is still partially up
            # yield f"event: error\\ndata: {json.dumps({'type': type(e).__name__, 'message': str(e), 'detail': 'Check server logs.'})}\\n\\n"
        finally:
            print("[MAPD_STREAM_FINALLY] Cleaning up MapD log stream resources...")
            if poller and socket and not socket.closed: # Check if socket is valid and not closed before unregister
                print("[MAPD_STREAM_FINALLY] Attempting to unregister poller.")
                try:
                    if socket in poller.sockets: # Check if socket is actually registered
                         poller.unregister(socket)
                         print("[MAPD_STREAM_FINALLY] Poller unregistered.")
                    else:
                         print("[MAPD_STREAM_FINALLY] Socket not found in poller, no unregister needed.")
                except KeyError:
                    print("[MAPD_STREAM_FINALLY] Socket already unregistered (KeyError).")
                except Exception as e_unreg:
                     print(f"[MAPD_STREAM_FINALLY] Error unregistering poller: {type(e_unreg).__name__}: {e_unreg}")

            if socket and not socket.closed:
                print("[MAPD_STREAM_FINALLY] Closing ZMQ socket.")
                socket.close()
                print("[MAPD_STREAM_FINALLY] ZMQ socket closed.")
            elif socket and socket.closed:
                print("[MAPD_STREAM_FINALLY] ZMQ socket was already closed.")
            else:
                print("[MAPD_STREAM_FINALLY] No ZMQ socket instance to close or was None.")
            print("[MAPD_STREAM_FINALLY] Cleanup finished.")

    return StreamingResponse(log_event_source(), media_type="text/event-stream")

# Model for the command execution request
class CommandRequest(BaseModel):
    command: str

# --- BEGIN CWD Management (Simple Global for Single User/Device Context) ---
# WARNING: This simple CWD management is not suitable for multi-user or multi-process environments.
# A more robust session-based CWD management would be needed for broader applications.
# For openpilot device context, this might be acceptable if concierge is single-instance.

# Global variable to store the current working directory for the terminal session
# Initialize to a sensible default, e.g., the openpilot directory or root.
# Ensure this path exists on the device.
_terminal_cwd = Path("/data/openpilot")
if not _terminal_cwd.is_dir(): # Fallback if /data/openpilot doesn't exist
    _terminal_cwd = Path("/")

# Helper to get the CWD as a string
def get_current_terminal_cwd_str() -> str:
    global _terminal_cwd
    return str(_terminal_cwd)

# Helper to attempt to change CWD
def set_current_terminal_cwd(new_path_str: str) -> tuple[bool, str]:
    global _terminal_cwd
    current_original_cwd = Path.cwd() # Save python process CWD
    target_path = Path(new_path_str)

    try:
        # Attempt to change directory to validate and resolve the path
        # We use a temporary chdir for python's process to validate,
        # but the _terminal_cwd is what subprocess will use.
        if not target_path.is_absolute():
            # Convert relative path to absolute based on current _terminal_cwd
            target_path = (_terminal_cwd / target_path).resolve()
        else:
            target_path = target_path.resolve() # Resolve an absolute path (e.g. removes ../)

        if not target_path.is_dir():
            return False, f"cd: no such file or directory: {new_path_str}"

        # Validate if we can actually chdir to it (permission check)
        os.chdir(target_path) # This changes the CWD of the FastAPI *worker process*
        _terminal_cwd = Path.cwd() # Update our stored CWD to the new, resolved path
        message = f"Changed directory to {str(_terminal_cwd)}"
        success = True
    except FileNotFoundError:
        message = f"cd: no such file or directory: {new_path_str}"
        success = False
    except PermissionError:
        message = f"cd: permission denied: {new_path_str}"
        success = False
    except Exception as e:
        message = f"cd: error changing directory to {new_path_str}: {str(e)}"
        success = False
    finally:
        os.chdir(current_original_cwd) # IMPORTANT: Restore python process CWD

    return success, message
# --- END CWD Management ---

# Endpoint to execute a shell command
@app.post("/api/execute-command")
async def execute_command_endpoint(payload: CommandRequest) -> Dict[str, Any]:
    debug_messages = []
    command_to_run = payload.command.strip() # Ensure leading/trailing whitespace is removed

    current_subprocess_cwd = get_current_terminal_cwd_str()
    debug_messages.append(f"[API_CMD] Current CWD for subprocess: {current_subprocess_cwd}")
    debug_messages.append(f"[API_CMD] Received raw command: '{command_to_run}'")

    if not command_to_run:
        debug_messages.append("[API_CMD] Error: Command cannot be empty.")
        # Return current CWD even for empty command errors
        return {"error": "Command cannot be empty", "debug_messages": debug_messages, "cwd": current_subprocess_cwd, "exit_code": -100}

    # --- CD Command Handling ---
    original_command_for_display = command_to_run # Save before potential modification for ls

    if command_to_run.startswith("cd ") or command_to_run == "cd":
        parts = shlex.split(command_to_run) # Use shlex to handle spaces/quotes in paths
        target_dir = ""
        if len(parts) > 1:
            target_dir = parts[1]
        elif command_to_run == "cd": # `cd` alone usually goes to home, let's try our _terminal_cwd's parent or root
            # For simplicity, `cd` without args could go to the initial _terminal_cwd or a predefined home.
            # Let's make `cd` alone go to the initial default directory `/data/openpilot` for now.
            # More sophisticated handling would involve a concept of $HOME for the terminal session.
            initial_default_dir = Path("/data/openpilot")
            if not initial_default_dir.is_dir(): initial_default_dir = Path("/")
            target_dir = str(initial_default_dir)
            debug_messages.append(f"[API_CMD] 'cd' without args, targeting default: {target_dir}")

        if not target_dir: # e.g. if command was just "cd " with spaces
             # No directory specified, could treat as no-op or error. Let's make it a no-op for now.
            debug_messages.append("[API_CMD] 'cd' with no target directory. No operation performed.")
            return {
                "command_executed": command_to_run,
                "stdout": "",
                "stderr": "",
                "exit_code": 0,
                "cwd": current_subprocess_cwd, # Return current CWD
                "debug_messages": debug_messages
            }

        debug_messages.append(f"[API_CMD] Intercepted 'cd' command. Target: '{target_dir}'")
        success, message = set_current_terminal_cwd(target_dir)
        new_cwd_str = get_current_terminal_cwd_str() # Get potentially updated CWD
        debug_messages.append(f"[API_CMD] cd result: success={success}, message='{message}', new CWD for session: {new_cwd_str}")

        return {
            "command_executed": command_to_run,
            "stdout": "" if success else "",
            "stderr": message if not success else "",
            "exit_code": 0 if success else 1, # Standard exit code for failed cd
            "cwd": new_cwd_str, # Return the new CWD
            "debug_messages": debug_messages
        }
    # --- END CD Command Handling ---

    # --- LS Color Handling ---
    # If the command is 'ls' or starts with 'ls ', inject '--color=always'
    # This is a simplified approach; robustly adding flags to any part of a complex shell command is harder.
    is_ls_command = False
    if command_to_run.startswith("ls ") or command_to_run == "ls":
        is_ls_command = True
        parts = shlex.split(command_to_run)
        # Check if a color flag is already present
        has_color_flag = any(part.startswith("--color") for part in parts)
        if not has_color_flag:
            # Insert --color=always after the 'ls' command itself
            if parts[0] == "ls":
                parts.insert(1, "--color=always")
            # If ls is part of a more complex command, this might not be the right place,
            # but for simple `ls` or `ls -l`, etc., this is okay.
            command_to_run = shlex.join(parts)
            debug_messages.append(f"[API_CMD] Modified command for color output: {command_to_run}")
    # --- END LS Color Handling ---

    try:
        process = subprocess.run(
            command_to_run,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=current_subprocess_cwd # Use the stored CWD for the subprocess
        )
        stdout = process.stdout.strip()
        stderr = process.stderr.strip()
        exit_code = process.returncode

        debug_messages.append(f"[API_CMD] STDOUT: {stdout}") # This will now contain ANSI codes for ls
        debug_messages.append(f"[API_CMD] STDERR: {stderr}")
        debug_messages.append(f"[API_CMD] Exit Code: {exit_code}")

        return {
            "command_executed": original_command_for_display, # Return the command as typed by user
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "cwd": current_subprocess_cwd,
            "is_ls_command": is_ls_command, # Add flag for frontend
            "debug_messages": debug_messages
        }
    except subprocess.TimeoutExpired:
        timeout_msg = f"Error: Command '{original_command_for_display}' timed out after 30 seconds."
        debug_messages.append(f"[API_CMD] {timeout_msg}")
        return {
            "command_executed": original_command_for_display,
            "stdout": "",
            "stderr": timeout_msg,
            "exit_code": -1,
            "cwd": current_subprocess_cwd,
            "is_ls_command": False,
            "debug_messages": debug_messages
        }
    except Exception as e:
        error_message = f"General error executing command '{original_command_for_display}': {str(e)}"
        debug_messages.append(f"[API_CMD] {error_message}")
        return {
            "command_executed": original_command_for_display,
            "stdout": "",
            "stderr": error_message,
            "exit_code": -2,
            "cwd": current_subprocess_cwd,
            "is_ls_command": False,
            "debug_messages": debug_messages
        }

# New endpoints for crash logs
@app.get("/api/crash-logs")
async def list_crash_logs() -> Dict[str, Any]:
    debug_messages = []
    debug_messages.append(f"[API] list_crash_logs: Attempting to list logs from {CRASH_LOGS_DIR}")
    try:
        resolved_path = CRASH_LOGS_DIR.resolve()
        debug_messages.append(f"[API] Resolved path: {resolved_path}")
        exists = CRASH_LOGS_DIR.exists()
        is_dir = CRASH_LOGS_DIR.is_dir()
        debug_messages.append(f"[API] Path {CRASH_LOGS_DIR} exists: {exists}, Is directory: {is_dir}")

        if not exists:
            debug_messages.append(f"[API] CRASH_LOGS_DIR {CRASH_LOGS_DIR} does not exist.")
            return {"files": [], "debug_messages": debug_messages}
        if not is_dir:
            debug_messages.append(f"[API] CRASH_LOGS_DIR {CRASH_LOGS_DIR} is not a directory.")
            return {"files": [], "debug_messages": debug_messages}

        # Try listing with os.listdir for more raw feedback
        try:
            raw_listing = os.listdir(CRASH_LOGS_DIR)
            debug_messages.append(f"[API] os.listdir output for {CRASH_LOGS_DIR}: {raw_listing}")
        except Exception as e_listdir:
            debug_messages.append(f"[API] Error during os.listdir for {CRASH_LOGS_DIR}: {str(e_listdir)}")
            # Continue, but note the error, glob might still work or provide more info

        txt_files = list(CRASH_LOGS_DIR.glob("*.txt"))
        log_files = list(CRASH_LOGS_DIR.glob("*.log"))
        log_files_found_by_glob = list(set(txt_files + log_files)) # Combine and remove duplicates

        debug_messages.append(f"[API] Files found by glob ('*.txt', '*.log'): {len(log_files_found_by_glob)}")
        if not log_files_found_by_glob:
            debug_messages.append(f"[API] No *.txt or *.log files found in {CRASH_LOGS_DIR}.")
            # Potentially list all files if no .txt or .log files are found, for more context
            all_files_in_dir = list(CRASH_LOGS_DIR.glob("*"))
            debug_messages.append(f"[API] All items found by {CRASH_LOGS_DIR.name}.glob('*'): {len(all_files_in_dir)}")
            for f_idx, f_path in enumerate(all_files_in_dir):
                debug_messages.append(f"[API] All item {f_idx}: {f_path.name} (Is file: {f_path.is_file()})")
        else:
            for f_idx, f_path in enumerate(log_files_found_by_glob): # Ensure this iterates over the combined list
                debug_messages.append(f"[API] Globbed file {f_idx}: {f_path.name}")

        log_files_data = []
        for file_path_obj in log_files_found_by_glob:
            debug_messages.append(f"[API] Processing globbed file: {file_path_obj.name}")
            try:
                stat_info = file_path_obj.stat()
                log_files_data.append({
                    "name": file_path_obj.name,
                    "size": f"{stat_info.st_size / 1024:.1f} KB",
                    "date": datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
                debug_messages.append(f"[API] Successfully statted {file_path_obj.name}")
            except Exception as e_stat:
                debug_messages.append(f"[API] Error statting file {file_path_obj.name}: {str(e_stat)}")

        log_files_data.sort(key=lambda x: datetime.datetime.strptime(x["date"], "%Y-%m-%d %H:%M:%S"), reverse=True)
        debug_messages.append(f"[API] Returning {len(log_files_data)} log files after processing and sorting.")
        return {"files": log_files_data, "debug_messages": debug_messages}

    except Exception as e:
        debug_messages.append(f"[API] General error in list_crash_logs: {str(e)}")
        # Construct detail string with all debug messages for the HTTPException
        error_detail = "\n".join(debug_messages)
        raise HTTPException(status_code=500, detail=f"[API] Error listing crash logs:\n{error_detail}")

@app.get("/api/crash-logs/{filename}")
async def get_crash_log(filename: str) -> PlainTextResponse:
    """Returns the content of a specific crash log file."""
    file_path = CRASH_LOGS_DIR / filename

    # Security check to prevent directory traversal
    if not file_path.is_relative_to(CRASH_LOGS_DIR) or not file_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    try:
        with open(file_path, "r") as f:
            return PlainTextResponse(f.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")

# Helper function to parse service names from log.capnp
def parse_capnp_services() -> Dict[str, List[str]]:
    capnp_services = []
    custom_services = []
    print(f"[SERVICE_PARSER_DEBUG] Attempting to parse: {LOG_CAPNP_PATH}")
    try:
        with open(LOG_CAPNP_PATH, "r") as f:
            content = f.read()
        print(f"[SERVICE_PARSER_DEBUG] Read {LOG_CAPNP_PATH}, content length: {len(content)}")

        # Regex to find the Event struct, allowing for an optional @id
        event_struct_regex = r"struct Event(?:\s*@[\w\d]+)?\s*{([\s\S]*?)}"
        event_struct_match = re.search(event_struct_regex, content, re.DOTALL)

        if event_struct_match:
            print("[SERVICE_PARSER_DEBUG] Found Event struct match.")
            event_struct_content = event_struct_match.group(1)
            print(f"[SERVICE_PARSER_DEBUG] Event struct content snippet (first 1000 chars):\n{event_struct_content[:1000]}")

            # Directly find service definitions within the whole Event struct content
            service_matches = re.finditer(r"\s*(\w+)\s*@\d+\s*:\s*([\w.]+)\s*;", event_struct_content)
            services_found_count = 0
            for match in service_matches:
                services_found_count += 1
                service_name = match.group(1)
                data_type = match.group(2)
                print(f"[SERVICE_PARSER_DEBUG] Raw match: Name='{service_name}', Type='{data_type}'")

                if "DEPRECATED" in service_name.upper() or service_name.endswith("DEPRECATED"):
                    print(f"[SERVICE_PARSER_DEBUG] Skipping deprecated: {service_name}")
                    continue
                if service_name in ["sendcan", "can", "logMessage", "errorLogMessage"]:
                    print(f"[SERVICE_PARSER_DEBUG] Skipping internal/common: {service_name}")
                    continue

                if data_type.startswith("Custom."):
                    print(f"[SERVICE_PARSER_DEBUG] Adding to custom_services: {service_name}")
                    custom_services.append(service_name)
                elif not data_type.startswith("Legacy."):
                    print(f"[SERVICE_PARSER_DEBUG] Adding to capnp_services: {service_name}")
                    capnp_services.append(service_name)
                else:
                    print(f"[SERVICE_PARSER_DEBUG] Skipping legacy non-custom: {service_name} (Type: {data_type})")
            print(f"[SERVICE_PARSER_DEBUG] Total raw service matches found: {services_found_count}")
        else:
            print("[SERVICE_PARSER] Could not find Event struct in log.capnp")

    except FileNotFoundError:
        print(f"[SERVICE_PARSER] Error: {LOG_CAPNP_PATH} not found.")
    except Exception as e:
        print(f"[SERVICE_PARSER] Error parsing log.capnp: {e}")

    print(f"[SERVICE_PARSER_DEBUG] Returning: capnp_services={len(capnp_services)}, custom_services={len(custom_services)}")
    return {"capnp_services": sorted(list(set(capnp_services))), "custom_services": sorted(list(set(custom_services)))}

def main():
    # This function is called by manager.py
    import uvicorn
    app_module_path = "selfdrive.chauffeur.concierge.main:app"
    uvicorn.run(app_module_path,
                host="0.0.0.0",
                port=5055,
                log_level="info")

if __name__ == "__main__":
    import uvicorn
    import sys
    import os # Added for path manipulation and directory creation
    from datetime import datetime
    from pathlib import Path # Ensure Path is imported if not already in global scope of __main__

    # BASE is defined globally: BASE = Path(__file__).resolve().parent
    LOG_DIR = BASE / "logs"
    log_file_path = LOG_DIR / "concierge_server.log"

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    log_file_handle = None

    try:
        print(f"[CONCIERGE_SETUP_ATTEMPT] Attempting to set up logging.", file=original_stdout)
        print(f"[CONCIERGE_SETUP_ATTEMPT] Base path: {BASE}", file=original_stdout)
        print(f"[CONCIERGE_SETUP_ATTEMPT] Log directory targeted: {LOG_DIR}", file=original_stdout)

        if not LOG_DIR.exists():
            print(f"[CONCIERGE_SETUP_ATTEMPT] Log directory {LOG_DIR} does not exist. Attempting to create it.", file=original_stdout)
            try:
                LOG_DIR.mkdir(parents=True, exist_ok=True)
                print(f"[CONCIERGE_SETUP_ATTEMPT] Successfully created log directory: {LOG_DIR}", file=original_stdout)
            except Exception as e_mkdir:
                print(f"[CONCIERGE_SETUP_FAIL] Failed to create log directory {LOG_DIR}: {e_mkdir}", file=original_stderr)
                # Continue without file logging if directory creation fails
                raise # Re-raise to prevent starting server if logging dir is critical

        print(f"[CONCIERGE_SETUP_ATTEMPT] Server output will be logged to: {log_file_path}", file=original_stdout)
        log_file_handle = open(log_file_path, 'a')
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file_handle.write(f"\n--- Server process started at {timestamp} ---\n")
        log_file_handle.flush()

        sys.stdout = log_file_handle
        sys.stderr = log_file_handle

        print(f"[CONCIERGE_SETUP_SUCCESS] stdout and stderr redirected to {log_file_path}") # This goes to the log file

    except Exception as e_log_setup:
        print(f"[CONCIERGE_SETUP_FAIL] FAILED TO SETUP FILE LOGGING: {e_log_setup}", file=original_stderr)
        print(f"[CONCIERGE_SETUP_FAIL] Server will run with console logging only.", file=original_stderr)
        # Reset to original streams if redirection partially occurred and then failed
        if sys.stdout == log_file_handle and log_file_handle is not None: sys.stdout = original_stdout
        if sys.stderr == log_file_handle and log_file_handle is not None: sys.stderr = original_stderr
        if log_file_handle is not None: log_file_handle.close(); log_file_handle = None # Ensure closed if opened

    # Server execution block
    server_exit_code = 0
    try:
        should_reload = "--dev" in sys.argv
        app_module_path = "selfdrive.chauffeur.concierge.main:app" # Moved here for clarity

        print(f"[UVICORN_START] Starting Uvicorn for {app_module_path}...") # Goes to log file or console
        uvicorn.run(app_module_path,
                    host="0.0.0.0",
                    port=5055,
                    log_level="info",
                    reload=should_reload,
                    reload_dirs=["selfdrive/chauffeur/concierge"] if should_reload else None)
    except Exception as e_main:
        print_target = original_stderr if log_file_handle and sys.stderr == log_file_handle else sys.stderr
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_msg = f"[{current_time}] CRITICAL ERROR in __main__ during uvicorn.run: {type(e_main).__name__}: {e_main}"
        print(error_msg, file=print_target)
        if log_file_handle: # Also try to write to log file if open
            print(error_msg, file=log_file_handle)
        import traceback
        traceback.print_exc(file=print_target)
        if log_file_handle:
            traceback.print_exc(file=log_file_handle)
        server_exit_code = 1 # Indicate error
    finally:
        final_message_target = sys.stdout # This will be the log file if redirection was successful, else original stdout
        if final_message_target == original_stderr : final_message_target = original_stdout # safety for rare case

        print(f"[UVICORN_END] Uvicorn process for {app_module_path} has exited.", file=final_message_target)

        if log_file_handle:
            print("[CONCIERGE_SHUTDOWN_LOG_FILE] Server process ended or uvicorn.run exited. Restoring streams.", file=final_message_target)
            timestamp_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_file_handle.write(f"--- Server process ended or streams restored at {timestamp_end} ---\n")
            log_file_handle.flush()
            log_file_handle.close()
            # Restore original stdout/stderr after log file is closed
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            print("[CONCIERGE_SHUTDOWN_CONSOLE] stdout/stderr restored. Log file closed.", file=original_stdout)
        else:
            print("[CONCIERGE_SHUTDOWN_CONSOLE] Server process ended. File logging was not active.", file=original_stdout)

        if server_exit_code != 0:
            print(f"[CONCIERGE_EXIT] Exiting with code {server_exit_code} due to critical error during server run.", file=original_stderr)
            # sys.exit(server_exit_code) # Optionally force exit code