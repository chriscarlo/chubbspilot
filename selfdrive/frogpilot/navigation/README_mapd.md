# mapd Integration

This directory contains the Python wrapper and integration for the Go-based mapd daemon.

## Overview

The mapd system consists of:
1. **mapd binary** - Go daemon that processes OpenStreetMap data
2. **mapd.py** - Python wrapper that manages the mapd process and bridges to cereal messaging
3. **build_mapd.sh** - Build script for compiling the mapd binary

## Building mapd Binary

### Option 1: Download pre-built binary (recommended)
```bash
cd /data/openpilot/selfdrive/frogpilot/navigation
./download_mapd.sh
```

This will download the appropriate binary for your architecture from the official releases.

### Option 2: Build from source (for development)
```bash
cd /data/openpilot/selfdrive/frogpilot/navigation
./build_mapd.sh
```

Requirements:
- Go 1.19+ installed
- Internet connection (for Go module downloads)

### Manual download
You can also manually download binaries from:
https://github.com/pfeiferj/mapd/releases

For comma device (ARM64), download `mapd-linux-arm64` and rename to `mapd`.

## Data Flow

1. **locationd** → writes GPS data to `LastGPSPosition` param
2. **mapd binary** → reads GPS, processes map data, writes to params:
   - `RoadName` - Current road name
   - `MapSpeedLimit` - Current speed limit
   - `MapTargetVelocities` - Turn speeds for MTSC
   - `MapCurvatures` - Road curvature data
3. **mapd.py bridge** → reads params, publishes `liveMapData` messages
4. **MTSC** → subscribes to `liveMapData` for turn speed control

## Testing

Run the integration test:
```bash
python test_mapd_integration.py
```

## Troubleshooting

1. **mapd binary not found**: Run `build_mapd.sh` or download binary
2. **No map data**: Ensure GPS fix and map tiles downloaded for area
3. **MTSC not receiving data**: Check `liveMapData` messages with `logcat`