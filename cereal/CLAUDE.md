# CLAUDE.md - Cereal Directory

Inter-process communication (IPC) message definitions and messaging infrastructure.

## Message Passing Architecture

Inter-process communication in openpilot uses a sophisticated messaging system:

- **Cap'n Proto** for serialization (cereal/)
- **ZeroMQ** for transport (msgq)
- **Services** defined in cereal/services.py
- **Manager** orchestrates all processes (system/manager/)

## Key Components

### Message Definitions
- **log.capnp** - Primary message schema definitions
- **car.capnp** - Vehicle-specific message types
- **custom.capnp** - Custom message extensions
- **legacy.capnp** - Legacy message compatibility

### Services Configuration
- **services.py** - Service definitions and port assignments
- Defines all inter-process communication endpoints
- Specifies message types, frequencies, and reliability requirements

### Messaging Infrastructure
- **messaging/** - Core messaging implementation
- **bridge.cc** - C++ messaging bridge
- **socketmaster.cc** - Socket management
- **messaging.h** - C++ header definitions

## Message Types

The system handles various categories of messages:

- **Control Messages** - Vehicle control commands and status
- **Sensor Data** - Camera, radar, GPS, IMU data
- **Perception Output** - Object detection, lane lines, path planning
- **System Status** - Process health, hardware status, diagnostics
- **User Interface** - UI state, user inputs, alerts

## Cross-Language Support

Messages are designed to work across multiple languages:
- **Python** - Primary development language
- **C++** - Performance-critical components
- **Cap'n Proto** provides language-agnostic serialization

## Protocol Buffer Compilation

The build system automatically compiles .capnp files:
- Uses protoc compiler for schema generation
- Supports multiple architectures (x86_64, larch64)
- Platform-specific protoc binaries in build system

## Development Guidelines

### Adding New Messages
1. Define message schema in appropriate .capnp file
2. Add service definition to services.py if needed
3. Update messaging code to handle new message type
4. Test across all target platforms

### Message Design Principles
- Keep messages lightweight and well-structured
- Use appropriate data types for efficiency
- Consider backward compatibility
- Document message purpose and usage

## Building

```bash
# Build cereal components
scons cereal/

# Build messaging system
scons cereal/messaging/
```

## Testing

```bash
# Run messaging tests
pytest cereal/messaging/tests/

# Test message serialization
pytest cereal/
```

## Cross-Platform Notes

- **Protoc Architecture Support**: Dual-architecture protoc v27.1 support
- **Platform Detection**: Automatically selects correct protoc binary
- **TICI Compatibility**: Fixed "Exec format error" issues on device
- **Cross-compilation**: Supports building messages for target architecture