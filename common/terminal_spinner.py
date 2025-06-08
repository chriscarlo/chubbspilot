#!/usr/bin/env python3
"""
Terminal-based boot UI to replace the graphical spinner.
Shows actual boot progress and system initialization status.
"""

import os
import subprocess
import time
import sys

# Add openpilot to path if needed
if '/data/openpilot' not in sys.path:
    sys.path.insert(0, '/data/openpilot')

try:
    from openpilot.common.basedir import BASEDIR
except ImportError:
    # Fallback for testing
    BASEDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TerminalSpinner:
  def __init__(self):
    self.terminal_proc = None
    self.services = {}
    self.start_time = time.time()
    
    try:
      # Use our new terminal boot UI instead of spinner
      self.terminal_proc = subprocess.Popen(
        ["./terminal_boot"],
        stdin=subprocess.PIPE,
        cwd=os.path.join(BASEDIR, "selfdrive", "ui", "terminal_boot"),
        close_fds=True
      )
    except OSError:
      # Fallback to original spinner if terminal UI not available
      print("Terminal boot UI not found, falling back to spinner")
      try:
        self.terminal_proc = subprocess.Popen(
          ["./spinner"],
          stdin=subprocess.PIPE,
          cwd=os.path.join(BASEDIR, "selfdrive", "ui"),
          close_fds=True
        )
      except OSError:
        self.terminal_proc = None

  def __enter__(self):
    return self

  def update(self, text: str):
    """Update phase or service status."""
    if self.terminal_proc is not None:
      try:
        self.terminal_proc.stdin.write(text.encode('utf8') + b"\n")
        self.terminal_proc.stdin.flush()
      except BrokenPipeError:
        pass

  def update_progress(self, cur: float, total: float):
    """Update progress percentage."""
    self.update(str(round(100 * cur / total)))

  def update_service(self, service: str, status: str, message: str = ""):
    """Update specific service status."""
    # Format: "service:status:message"
    self.update(f"{service}:{status}:{message}")
  
  def report_error(self, service: str, error_msg: str, traceback_str: str = "", 
                   file_path: str = "", line_num: int = 0, suggested_fix: str = ""):
    """Report detailed error information for a service."""
    # Parse traceback to extract useful info if provided
    if traceback_str and not file_path:
      # Try to extract file and line from traceback
      import re
      file_match = re.search(r'File "([^"]+)", line (\d+)', traceback_str)
      if file_match:
        file_path = file_match.group(1)
        line_num = int(file_match.group(2))
    
    # Generate suggested fixes based on common errors
    if not suggested_fix:
      suggested_fix = self._suggest_fix(error_msg, file_path)
    
    # Format: "service:error:message:file:line:details:suggested_fix"
    # Use | as delimiter to avoid conflicts with file paths
    formatted_error = f"{service}:error:{error_msg}:{file_path}:{line_num}:{traceback_str}:{suggested_fix}"
    self.update(formatted_error)
  
  def _suggest_fix(self, error_msg: str, file_path: str) -> str:
    """Generate suggested fixes based on common error patterns."""
    error_lower = error_msg.lower()
    
    # Common error patterns and fixes
    if "permission denied" in error_lower:
      return "Check file permissions. Try: sudo chmod +x <file>"
    elif "no such file or directory" in error_lower:
      return "Missing file. Check if all files were properly installed."
    elif "import error" in error_lower or "modulenotfounderror" in error_lower:
      return "Missing Python module. Try: pip install <module_name>"
    elif "can" in error_lower and ("timeout" in error_lower or "error" in error_lower):
      return "CAN communication issue. Check panda connection and power."
    elif "camera" in error_lower:
      return "Camera initialization failed. Check camera connections."
    elif "memory" in error_lower or "oom" in error_lower:
      return "Out of memory. Try rebooting or checking for memory leaks."
    elif "segmentation fault" in error_lower or "segfault" in error_lower:
      return "Memory corruption. Check for null pointers or buffer overflows."
    elif file_path and "selfdrive/car" in file_path:
      return "Vehicle interface error. Check car compatibility."
    else:
      return "Check logs in /data/log/ for more details."
    
  def set_phase(self, phase: str):
    """Set current boot phase."""
    self.update(phase)

  def close(self):
    if self.terminal_proc is not None:
      self.terminal_proc.kill()
      try:
        self.terminal_proc.communicate(timeout=2.)
      except subprocess.TimeoutExpired:
        print("WARNING: failed to kill terminal UI")
      self.terminal_proc = None

  def __del__(self):
    self.close()

  def __exit__(self, exc_type, exc_value, traceback):
    self.close()


# Quick demo/test
if __name__ == "__main__":
  with TerminalSpinner() as s:
    # Simulate boot sequence
    s.set_phase("HARDWARE INITIALIZATION")
    time.sleep(1)
    
    s.update_service("thermald", "starting", "Configuring thermal zones...")
    s.update_progress(10, 100)
    time.sleep(0.5)
    
    s.update_service("thermald", "running")
    s.update_service("pandad", "starting", "Initializing CAN bus...")
    s.update_progress(20, 100)
    time.sleep(0.5)
    
    s.update_service("pandad", "running")
    s.update_service("camerad", "starting", "Detecting cameras...")
    s.update_progress(30, 100)
    time.sleep(0.5)
    
    s.set_phase("LOADING VISION MODELS")
    s.update_service("camerad", "running", "3 cameras online")
    s.update_service("modeld", "starting", "Loading neural networks...")
    s.update_progress(50, 100)
    time.sleep(2)
    
    s.update_service("modeld", "running")
    s.update_service("controlsd", "starting")
    s.update_progress(70, 100)
    time.sleep(0.5)
    
    # Simulate an error to show error display
    s.report_error(
      service="controlsd",
      error_msg="RuntimeError: CAN Error: No messages received from panda",
      traceback_str="""Traceback (most recent call last):
  File "/data/openpilot/selfdrive/controls/controlsd.py", line 742, in main
    controls = Controls(sm, pm, CP)
  File "/data/openpilot/selfdrive/controls/controlsd.py", line 168, in __init__
    self.CI = get_car_interface(self.CP)
  File "/data/openpilot/selfdrive/car/car_helpers.py", line 142, in get_car_interface
    raise RuntimeError("CAN Error: No messages received from panda")
RuntimeError: CAN Error: No messages received from panda""",
      file_path="/data/openpilot/selfdrive/car/car_helpers.py",
      line_num=142
    )
    time.sleep(5)  # Give time to read error
    
    # Continue with other services to show mixed success/failure
    s.update_service("plannerd", "failed", "Dependency controlsd failed")
    s.update_service("radard", "running")
    
    s.set_phase("STARTING USER INTERFACE")
    s.update_service("ui", "starting", "Initializing display...")
    s.update_progress(90, 100)
    time.sleep(1)
    
    s.update_service("ui", "running")
    s.update_progress(100, 100)
    s.set_phase("BOOT COMPLETE - READY TO DRIVE")
    time.sleep(2)
    
  print("\nBoot sequence complete!")
  time.sleep(1)