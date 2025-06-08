#!/usr/bin/env python3
"""
Error handler for boot process - captures and reports detailed error information
to the terminal UI instead of just showing a failed status.
"""

import traceback
import sys
from typing import Optional
from openpilot.common.terminal_spinner import TerminalSpinner


class BootErrorHandler:
  """Captures and reports boot errors with actionable information."""
  
  def __init__(self, spinner: Optional[TerminalSpinner] = None):
    self.spinner = spinner
    
  def handle_service_error(self, service_name: str, exception: Exception):
    """Handle and report service startup errors."""
    if not self.spinner or not hasattr(self.spinner, 'report_error'):
      # Fallback to basic error reporting
      print(f"Error starting {service_name}: {str(exception)}")
      return
    
    # Get full traceback
    tb_str = traceback.format_exc()
    
    # Extract the most relevant frame from traceback
    tb_lines = traceback.format_tb(exception.__traceback__)
    if tb_lines:
      # Get the last (most specific) traceback entry
      last_frame = tb_lines[-1]
      
      # Parse file and line info
      import re
      match = re.search(r'File "([^"]+)", line (\d+)', last_frame)
      if match:
        error_file = match.group(1)
        error_line = int(match.group(2))
      else:
        error_file = ""
        error_line = 0
    else:
      error_file = ""
      error_line = 0
    
    # Generate error message
    error_msg = f"{type(exception).__name__}: {str(exception)}"
    
    # Report to terminal UI
    self.spinner.report_error(
      service=service_name,
      error_msg=error_msg,
      traceback_str=tb_str,
      file_path=error_file,
      line_num=error_line
    )
  
  def wrap_service_start(self, service_name: str, start_func, *args, **kwargs):
    """Wrap a service start function to capture errors."""
    try:
      return start_func(*args, **kwargs)
    except Exception as e:
      self.handle_service_error(service_name, e)
      raise


def capture_startup_errors(service_name: str):
  """Decorator to capture and report service startup errors."""
  def decorator(func):
    def wrapper(*args, **kwargs):
      try:
        return func(*args, **kwargs)
      except Exception as e:
        # Try to get spinner from global context or create new one
        try:
          from openpilot.common.terminal_spinner import TerminalSpinner
          spinner = TerminalSpinner()
          handler = BootErrorHandler(spinner)
          handler.handle_service_error(service_name, e)
        except:
          # Fallback to basic logging
          print(f"Error in {service_name}: {e}")
          traceback.print_exc()
        raise
    return wrapper
  return decorator


# Example usage in a service:
# @capture_startup_errors("modeld")
# def start_model_daemon():
#   import selfdrive.modeld.modeld
#   # ... startup code ...