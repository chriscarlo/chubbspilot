import datetime
import json

# --- Logging Utility ---
def format_value(value):
    if isinstance(value, (list, dict)):
        # For lists/dicts, use a compact JSON representation unless it's a known complex object
        if hasattr(value, '__dict__') and not isinstance(value, (list, dict, str, int, float, bool)):
            return str(value) # For complex objects, just use string representation
        return json.dumps(value, separators=(',', ':'))
    if isinstance(value, str) and (' ' in value or '=' in value or ',' in value or '"' in value):
        return f'"{value.replace("\"", "\\\"")}"'
    if isinstance(value, float):
        return f"{value:.4f}" # Format floats to 4 decimal places for brevity
    if value is None:
        return "None"
    return str(value)

def log_event(module_name: str, level: str, event_description: str, **kwargs):
    timestamp = datetime.datetime.utcnow().isoformat(timespec='milliseconds') + "Z"
    details = ", ".join(f"{key}={format_value(value)}" for key, value in kwargs.items())
    log_message = f"[{timestamp}] [{module_name.upper()}] [{level.upper()}] {event_description}: {details if details else 'No details'}"
    print(log_message, flush=True)
# --- End Logging Utility ---