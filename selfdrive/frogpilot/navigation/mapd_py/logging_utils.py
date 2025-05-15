import datetime
import json
import zmq

# ZMQ Log Publisher Setup
LOG_PUB_ADDR = "tcp://*:8607" # Port for mapd logs
_zmq_context = None
_zmq_log_publisher = None

def _initialize_zmq_publisher():
    global _zmq_context, _zmq_log_publisher
    if _zmq_log_publisher is None:
        _zmq_context = zmq.Context()
        _zmq_log_publisher = _zmq_context.socket(zmq.PUB)
        _zmq_log_publisher.bind(LOG_PUB_ADDR)
        # Allow some time for subscribers to connect if any are already waiting
        # This is less critical for PUB sockets usually but good practice
        # print(f"MapdPy Logging: ZMQ PUB socket bound to {LOG_PUB_ADDR}", flush=True) # Debug print

# --- Logging Utility ---
def format_value(value):
    if isinstance(value, (list, dict)):
        # For lists/dicts, use a compact JSON representation unless it's a known complex object
        if hasattr(value, '__dict__') and not isinstance(value, (list, dict, str, int, float, bool)):
            return str(value) # For complex objects, just use string representation
        return json.dumps(value, separators=(',', ':'))
    if isinstance(value, str) and (' ' in value or '=' in value or ',' in value or '"' in value):
        # Break out the replace operation to simplify the f-string for the linter
        processed_value = value.replace('"', '\\"')
        return f'"{processed_value}"'
    if isinstance(value, float):
        return f"{value:.4f}" # Format floats to 4 decimal places for brevity
    if value is None:
        return "None"
    return str(value)

def log_event(module_name: str, level: str, event_description: str, **kwargs):
    global _zmq_log_publisher
    if _zmq_log_publisher is None:
        _initialize_zmq_publisher()

    timestamp = datetime.datetime.utcnow().isoformat(timespec='milliseconds') + "Z"
    details = ", ".join(f"{key}={format_value(value)}" for key, value in kwargs.items())
    log_message = f"[{timestamp}] [{module_name.upper()}] [{level.upper()}] {event_description}: {details if details else 'No details'}"
    # print(log_message, flush=True) # Original print statement
    if _zmq_log_publisher is not None:
        try:
            _zmq_log_publisher.send_string(log_message)
        except zmq.error.ZMQError as e:
            # Fallback to print if ZMQ fails (e.g., during shutdown or if context is terminated)
            print(f"ZMQ SEND FAILED: {e}, LOG: {log_message}", flush=True)
    else:
        # Fallback if ZMQ somehow isn't initialized (should not happen with the check above)
        print(f"ZMQ NOT INITIALIZED, LOG: {log_message}", flush=True)

# --- End Logging Utility ---