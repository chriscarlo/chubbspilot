"""Application constants for Concierge"""

# Cereal messaging services we want to monitor
WANTED_SERVICES = ["deviceState", "carState", "thermal", "liveLocationKalman"]

# Default timeout values
DEFAULT_COMMAND_TIMEOUT = 30
DEFAULT_ZMQ_TIMEOUT = 1000
DEFAULT_POLL_INTERVAL = 0.25

# Path constants (relative to openpilot root)
CEREAL_RELATIVE_PATH = "cereal"
LOG_CAPNP_RELATIVE_PATH = "cereal/log.capnp"

# API response limits
MAX_LOG_LINES = 50
MAX_FILE_SIZE_MB = 10

# Process monitoring
MAX_CONCURRENT_PROCESSES = 10
PROCESS_CLEANUP_INTERVAL = 60