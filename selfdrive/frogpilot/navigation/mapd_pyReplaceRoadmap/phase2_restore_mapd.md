# Phase 2: Restore and Integrate the Original `mapd` System

Next, we bring back the original mapd (the one used in the `upstream-chubbs` branch and other forks) so that our system has a map data provider again:

## 1. Retrieve the original `mapd` implementation
In the `upstream-chubbs` branch (or the FrogPilot upstream), the mapd process was likely represented by a module or script at `selfdrive/frogpilot/navigation/mapd` (possibly a Python launcher for the Go binary). Bring in the code from that branch. This might include:

* A Python file (e.g. `mapd.py`) that starts the mapd daemon or interacts with it.
* Any related utilities or config files (for example, if there's a script to update/download the `mapd` binary).
* Ensure we also have the latest `mapd` binary (v1.9.0 or later) available on the device. If upstream provided a static binary or an auto-update mechanism, include that.

## 2. Process configuration
Reinstate the mapd process in the manager's process list. In upstream FrogPilot, `mapd` was added to the process config as an always-on process. For example, FrogPilot's config shows: `PythonProcess("mapd", "selfdrive.frogpilot.navigation.mapd", always_run)`. In our repo's process config (likely `selfdrive/manager/process_config.py` or similar), re-add an entry for the `mapd` process matching the original. This ensures that on startup, the system will launch mapd automatically. We should also include any companion process if needed (for instance, FrogPilot uses a `frogpilot_process` for housekeeping – if that includes mapd management, bring that in as well).

## 3. Launching mapd
Decide how the mapd binary will be executed. Ideally, the `mapd` Python process acts as a wrapper:

* It may check for the presence of the mapd binary in a known location (e.g. `/data/openpilot/selfdrive/frogpilot/navigation/mapd` might contain the binary or a symlink).
* If the binary isn't present or is outdated, the process could download the latest release (the upstream implementation by @pfeiferj mentioned auto-updating mapd).
* Launch the mapd binary (via `subprocess.Popen`) and perhaps monitor it. The Python wrapper might simply exec the binary and let it run as a daemon process, or it might periodically ensure it's running.
* For now, use the same approach as in the upstream-chubbs branch so we don't have to design this from scratch. For example, if `frogpilot_process` in upstream checks GitHub for a new mapd release and downloads it, integrate that logic. Otherwise, include the binary in our repository and just run it.

## 4. Input data for mapd
The original mapd will need certain inputs to function:

* **GPS/location data**: In openpilot, the locationd service provides GPS via params or messaging. Mapd likely reads the current location (latitude/longitude). Ensure that the `mapd` process has access to this. Typically, the mapd daemon might read `LastGPSPosition` from the shared params (or subscribe to locationd outputs). Our integration should verify that `LastGPSPosition` param is being updated by locationd or navd. (Openpilot's `locationd` or `ubloxd` usually set this param; FrogPilot already uses it in MTSC, so it should exist).
* **Navigation route data**: If the user sets a destination, mapd needs the route. In FrogPilot, there might be a param like `NavDestination` or `NavRoute` that mapd reads, or it could get data from an online API/offline maps. Since FrogPilot supports offline maps, mapd might automatically use OpenStreetMap data around the car even without a set destination. We should confirm how mapd knows what route or road to process. Upstream references (like `pfeiferj/mapd` docs) indicate mapd has inputs for current location and optionally a route. We should ensure our integration passes those. Likely, no code changes are needed if we use FrogPilot's approach, as the mapd binary might internally query the device's current route or map data based on location.

## 5. Output channels
The original mapd likely outputs data through two possible channels:

* **Shared params (in `/dev/shm/params`)**: Evidence from MTSC code shows that mapd writes a JSON list to a param called `"MapTargetVelocities"` and the current position to `"LastGPSPosition"`. The mapd binary (via its `params.go`) probably updates those. We will rely on this mechanism. No additional coding is needed if the binary already does it. Just ensure that when mapd runs, these param values appear.
* **Cereal messaging (capnp)**: In older openpilot, mapd used a capnp message (`LiveMapData` in the log) with fields like curvature, speedLimit, etc. However, that struct was marked deprecated and many forks opted for the params/JSON approach instead. We will **not** attempt to revive capnp messaging for map data, as it's unnecessary complexity given FrogPilot's working solution. Instead, stick to the params-based output that our Python controllers already use.

## 6. Build & dependency adjustments
If integrating mapd requires any new dependencies (e.g. if the Python wrapper uses requests to download the binary, or if we need to include the binary in the build), take care of those. For example, if using an auto-update, ensure the device has network access or the URL (like GitHub API) is reachable. If bundling the binary, update any packaging scripts so that the binary is included in the release image.

## Success Criteria
By the end of Phase 2, the original mapd process should be running in our system (albeit outputting possibly to the shared params). We can test this by running openpilot on the device and checking that the `mapd` process is listed in running processes (via `tmux` or log output) and that it populates data (we expect entries for `LastGPSPosition` and `MapTargetVelocities` to update as we move).