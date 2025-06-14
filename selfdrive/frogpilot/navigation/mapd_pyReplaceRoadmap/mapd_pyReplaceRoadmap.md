Understood. I’ll develop a comprehensive roadmap for replacing `mapd_py` in the `exp04` branch with the legacy `mapd` from the `upstream-chubbs` branch. This will include recommendations on adjusting `mapd` or MTSC to ensure compatibility, a critique of both approaches, guidance for progressing toward unified MTSC/VTSC logic, and the introduction of suitable test scenarios to validate behavior.

I’ll also include implementation-level detail (e.g., suggested diffs, method designs, or class interface outlines) where critical, and leave space for artistic judgment where flexibility benefits downstream AI agents. I’ll get started and follow up when the plan is ready for review.


# Roadmap: Removing `mapd_py` and Unifying Turn Speed Controllers

## Design Decision: Modify `mapd` Output vs. Modify MTSC Input

**Pros of adapting `mapd` output:** By altering the original mapd’s output format to match what the Map Turn Speed Controller (MTSC) expects, we isolate changes to one module. This leverages upstream improvements to mapd (e.g. pfeiferj’s mapd v1.9.0 fixes) so that MTSC can directly benefit without complex rewrites. Keeping MTSC logic intact means we preserve its proven behaviors and simply feed it compatible data. Notably, FrogPilot’s experience shows that updating mapd can resolve MTSC issues (reducing the need for failsafe toggles). Aligning with the community-supported mapd makes future maintenance easier and lets us remove custom proto layers.

**Cons of adapting `mapd`:** If the original mapd is a compiled Go daemon, modifying its output might require some wrapper or changes in how it writes data (potentially more involved if we aren’t familiar with Go). However, since upstream forks have already integrated mapd via known interfaces (params and capnp), we can mostly reuse that approach.

**Pros of modifying MTSC instead:** Adjusting MTSC to accept whatever format the original mapd provides could mean fewer changes to mapd. But in our case, the original mapd’s outputs are well-defined (via on-device params or capnp messages), and our current MTSC is tailored to the experimental `mapd_py` and protobuf. Tweaking MTSC to a new interface would further diverge it from upstream FrogPilot logic, complicating future unification with VTSC.

**Decision – adapt mapd output:** It’s preferable to make `mapd` present data in the format MTSC already uses (or expects) rather than rewriting MTSC. This keeps the controller behavior stable and lets us drop the entire experimental proto framework. We will proceed by removing `mapd_py` and protobuf entirely, restoring the original mapd process, and ensuring it populates the same data channels that MTSC currently reads. In summary, we’ll **modify `mapd`’s output** to be compatible, rather than altering MTSC logic, unless minor tweaks are needed for integration.

## Phase 1: Remove `mapd_py` and Protobuf Infrastructure

This phase entails purging the experimental Python mapd implementation and any associated protobuf messaging from the codebase:

1. **Delete the `mapd_py` module:** Remove the entire directory `selfdrive/frogpilot/navigation/mapd_py` (and its contents) from the repository. This includes all Python files (e.g. any `__init__.py`, logic files) and any `.proto` definition files related to mapd. By removing this, we eliminate the experimental Go-based reimplementation that we no longer plan to use.

2. **Remove build and dependency entries:** If `mapd_py` introduced any build rules or was referenced in a build configuration (e.g. Bazel or custom build scripts), delete those references. Also remove any installation of protobuf libraries if they were added solely for `mapd_py`. For example, if a `requirements.txt` or pip installation added `protobuf` or if protoc compiler steps were added, they should be excised.

3. **Purge proto-generated code:** Delete any Python files auto-generated from `.proto` (for instance, files named like `*_pb2.py` if present). These are no longer needed once we drop protobuf messaging.

4. **Update imports and references:** Search the entire codebase for any references to `mapd_py` or its data structures. This includes places where MTSC or other modules may import `mapd_py` or use its outputs. Remove or update those references. After this, no part of the code should be trying to use `mapd_py` or protobuf messages. For instance, if MTSC was reading a proto message (like `MapData`), that logic should be removed or replaced with reading the data from the restored `mapd` (addressed in Phase 3). The goal is that the code compiles/runs with no mention of `mapd_py` remaining.

5. **Clean up parameters and settings:** If any persistent parameters or toggles were specific to `mapd_py` (for example, a param enabling the experimental mapd or controlling proto logging), remove those. This prevents unused settings from lingering. We want a clean slate where only the original mapd approach remains.

By the end of Phase 1, the codebase should have no `mapd_py` code or protobuf dependencies. It should be as if that experimental feature never existed, setting the stage for reintroducing the original mapd system.

## Phase 2: Restore and Integrate the Original `mapd` System

Next, we bring back the original mapd (the one used in the `upstream-chubbs` branch and other forks) so that our system has a map data provider again:

1. **Retrieve the original `mapd` implementation:** In the `upstream-chubbs` branch (or the FrogPilot upstream), the mapd process was likely represented by a module or script at `selfdrive/frogpilot/navigation/mapd` (possibly a Python launcher for the Go binary). Bring in the code from that branch. This might include:

   * A Python file (e.g. `mapd.py`) that starts the mapd daemon or interacts with it.
   * Any related utilities or config files (for example, if there’s a script to update/download the `mapd` binary).
   * Ensure we also have the latest `mapd` binary (v1.9.0 or later) available on the device. If upstream provided a static binary or an auto-update mechanism, include that.

2. **Process configuration:** Reinstate the mapd process in the manager’s process list. In upstream FrogPilot, `mapd` was added to the process config as an always-on process. For example, FrogPilot’s config shows: `PythonProcess("mapd", "selfdrive.frogpilot.navigation.mapd", always_run):contentReference[oaicite:2]{index=2}`. In our repo’s process config (likely `selfdrive/manager/process_config.py` or similar), re-add an entry for the `mapd` process matching the original. This ensures that on startup, the system will launch mapd automatically. We should also include any companion process if needed (for instance, FrogPilot uses a `frogpilot_process` for housekeeping – if that includes mapd management, bring that in as well).

3. **Launching mapd:** Decide how the mapd binary will be executed. Ideally, the `mapd` Python process acts as a wrapper:

   * It may check for the presence of the mapd binary in a known location (e.g. `/data/openpilot/selfdrive/frogpilot/navigation/mapd` might contain the binary or a symlink).
   * If the binary isn’t present or is outdated, the process could download the latest release (the upstream implementation by @pfeiferj mentioned auto-updating mapd).
   * Launch the mapd binary (via `subprocess.Popen`) and perhaps monitor it. The Python wrapper might simply exec the binary and let it run as a daemon process, or it might periodically ensure it’s running.
   * For now, use the same approach as in the upstream-chubbs branch so we don’t have to design this from scratch. For example, if `frogpilot_process` in upstream checks GitHub for a new mapd release and downloads it, integrate that logic. Otherwise, include the binary in our repository and just run it.

4. **Input data for mapd:** The original mapd will need certain inputs to function:

   * GPS/location data: In openpilot, the locationd service provides GPS via params or messaging. Mapd likely reads the current location (latitude/longitude). Ensure that the `mapd` process has access to this. Typically, the mapd daemon might read `LastGPSPosition` from the shared params (or subscribe to locationd outputs). Our integration should verify that `LastGPSPosition` param is being updated by locationd or navd. (Openpilot’s `locationd` or `ubloxd` usually set this param; FrogPilot already uses it in MTSC, so it should exist).
   * Navigation route data: If the user sets a destination, mapd needs the route. In FrogPilot, there might be a param like `NavDestination` or `NavRoute` that mapd reads, or it could get data from an online API/offline maps. Since FrogPilot supports offline maps, mapd might automatically use OpenStreetMap data around the car even without a set destination. We should confirm how mapd knows what route or road to process. Upstream references (like `pfeiferj/mapd` docs) indicate mapd has inputs for current location and optionally a route. We should ensure our integration passes those. Likely, no code changes are needed if we use FrogPilot’s approach, as the mapd binary might internally query the device’s current route or map data based on location.

5. **Output channels:** The original mapd likely outputs data through two possible channels:

   * **Shared params (in `/dev/shm/params`):** Evidence from MTSC code shows that mapd writes a JSON list to a param called `"MapTargetVelocities"` and the current position to `"LastGPSPosition"`. The mapd binary (via its `params.go`) probably updates those. We will rely on this mechanism. No additional coding is needed if the binary already does it. Just ensure that when mapd runs, these param values appear.
   * **Cereal messaging (capnp):** In older openpilot, mapd used a capnp message (`LiveMapData` in the log) with fields like curvature, speedLimit, etc. However, that struct was marked deprecated and many forks opted for the params/JSON approach instead. We will **not** attempt to revive capnp messaging for map data, as it’s unnecessary complexity given FrogPilot’s working solution. Instead, stick to the params-based output that our Python controllers already use.

6. **Build & dependency adjustments:** If integrating mapd requires any new dependencies (e.g. if the Python wrapper uses requests to download the binary, or if we need to include the binary in the build), take care of those. For example, if using an auto-update, ensure the device has network access or the URL (like GitHub API) is reachable. If bundling the binary, update any packaging scripts so that the binary is included in the release image.

By the end of Phase 2, the original mapd process should be running in our system (albeit outputting possibly to the shared params). We can test this by running openpilot on the device and checking that the `mapd` process is listed in running processes (via `tmux` or log output) and that it populates data (we expect entries for `LastGPSPosition` and `MapTargetVelocities` to update as we move).

## Phase 3: Adapt `mapd` Output for MTSC Compatibility

Now that the original mapd is in place, we ensure that its outputs line up exactly with what the MTSC code expects, making adjustments either in mapd’s data publication or in MTSC’s input handling:

1. **Ensure param keys and format match:** The MTSC controller in our code likely expects map data via shared params. From the existing MTSC logic (in `chauffeur_mtsc.py` or similar), we see it reads JSON from keys `"LastGPSPosition"` and `"MapTargetVelocities"`. We must confirm that our mapd process writes those exact keys in the same JSON structure:

   * `LastGPSPosition`: typically a JSON object like `{"latitude": ..., "longitude": ...}`. If mapd uses a different key or format for current position, adapt it. (Given both FrogPilot and our code refer to `LastGPSPosition`, this is likely consistent).
   * `MapTargetVelocities`: expected to be a JSON array of points, where each point has at least `latitude`, `longitude`, and a `velocity`. Our MTSC code iterates over this list. Check the actual output of mapd: if the keys differ (e.g. `speed` instead of `velocity`) or units differ (m/s vs MPH), we need to handle that. In FrogPilot’s case, they likely use m/s for velocity in this structure. We should verify (e.g. by checking pfeiferj’s documentation or printing a sample of `MapTargetVelocities` at runtime).

2. **Adapt mapd process if needed:** If we discover any mismatch, prefer to adjust in the mapd wrapper:

   * For example, if the mapd binary writes a different param name or format (though unlikely, since FrogPilot’s MTSC is working with it), we can add a small translator. Since the `mapd` process is written to always run, one approach is to modify the Python wrapper to normalize the output. However, since the binary likely writes directly to params, intercepting that might not be trivial. A better approach is to configure mapd via its inputs or settings to use the expected output. If pfeiferj’s mapd has flags or config (perhaps via a capnp/JSON toggle) to enable the FrogPilot-style output, ensure that’s enabled.
   * If absolutely required, a lightweight solution is to have a small Python loop (maybe as part of `frogpilot_process`) that watches for mapd’s output (like a different param or file) and copies it into `MapTargetVelocities` in the expected format. This is a fallback; ideally we won’t need this if versions align.

3. **Simplify MTSC code (if needed):** Our existing MTSC (chauffeur\_mtsc.py) might contain extra logic due to the previous `mapd_py` implementation. For instance, it might have been constructing proto messages or waiting on a protobuf signal. Now that we revert to the param approach, clean up MTSC:

   * Remove any code dealing with proto deserialization. Instead, ensure it reads from the params like FrogPilot’s does. If our MTSC was already modeled on FrogPilot’s, it may already do this reading (or we can replace it with FrogPilot’s MTSC logic as a reference).
   * Verify the MTSC toggle. FrogPilot has a param “MTSCEnabled” (likely we do too). Ensure this still controls whether MTSC runs. If previously `mapd_py` used a different flag, unify it to the standard one.
   * Check how MTSC determines “curve ahead”. In FrogPilot’s MTSC, after reading target velocities, it calculates whether a slower speed is needed and returns a target speed. Our MTSC should now behave the same. If there were any differences (say, `mapd_py` had additional criteria), consider removing them to match the simpler logic.
   * One known difference: if `mapd_py` used protobuf messages, MTSC might have waited for a message on a socket rather than continuously polling params. With the param method, MTSC can be called every planner cycle (the code likely already does this in the planner update). Ensure that the planner or control loop is invoking MTSC’s `target_speed()` regularly (this should already be true, as in FrogPilot’s `frogpilot_planner.py` it calls `mtsc.target_speed(...)` each cycle).

4. **Verify end-to-end data flow:** With mapd running and MTSC consuming, test on a bench or device:

   * Simulate or run the car with a navigation route (or on a road with offline map data) and print out MTSC’s computed `mtsc_target`. It should go from 0 (or cruise speed) down to some value when approaching a curve.
   * Log the content of `MapTargetVelocities` to ensure it contains plausible upcoming speeds. For example, on a highway, many entries might have `velocity` equal to the speed limit, and on a tight upcoming turn, an entry might have a lower `velocity` (indicating slow down).
   * Confirm that MTSC picks up the lowest needed speed. If something’s off (say, no slowdowns trigger), we may need to adjust how far ahead mapd provides data or the threshold in MTSC.
   * If the car has no navigation route set, test if mapd still produces data for the current road. Ideally, it should (using the current road’s geometry), enabling MTSC on “random drive” without a destination. If it doesn’t, note that MTSC will effectively be idle when not navigating. (This could be acceptable, but FrogPilot’s offline maps likely means it *does* always have data from OSM.)

By completing Phase 3, the original mapd and the MTSC consumer should work in tandem. We will have effectively swapped out the internals of MTSC’s data source without the rest of the control stack noticing a difference (except improved reliability). MTSC will directly use mapd’s outputs (via shared params) as it did in upstream FrogPilot. The protobuf-based communication channel is gone, simplifying the system.

## Phase 4: Unify MTSC and VTSC Logic

With a functioning Map Turn Speed Controller and Vision Turn Speed Controller (VTSC) both in place, attention turns to unifying these into a single Turn Speed Controller logic. The long-term goal is one controller that uses curvature input from either maps or vision as available. Achieving full unification will likely be iterative:

1. **Compare current implementations:** Start by reviewing `chauffeur_mtsc.py` and `chauffeur_vtsc.py` side-by-side. Document what each is doing:

   * How does VTSC determine a curve and target speed? (Likely using model path curvature or lane curvature from the model outputs.)
   * How does MTSC determine target speed from map data? (Now it uses the approach restored from FrogPilot.)
   * Identify differences: e.g., VTSC might have a “sensitivity” setting to decide what curvature triggers a slowdown, whereas MTSC relies on map data and had a “model curvature failsafe” toggle to avoid false positives. There may also be differences in how the target speed is smoothed or applied (VTSC might engage more gradually).
   * Note any common elements: ultimately both produce a target speed (or speed limit) for the planner to use when approaching a curve.

2. **Abstract the input – curvature as common metric:** Plan a refactor where both controllers feed a common logic with a measure of curve severity. We treat curvature as the “black box” input:

   * For VTSC: compute curvature from vision (the model’s predicted path). In code, FrogPilot already computes `road_curvature = calculate_road_curvature(modelData, v_ego)` each cycle. Ensure we have a similar function (if not, we can adopt FrogPilot’s).
   * For MTSC: compute curvature from map data. The mapd output gives target speeds, but we can derive curvature as well. FrogPilot’s MTSC update in v0.9.7 introduced a direct curvature calculation from map points. We should incorporate something similar so that we have an estimate of road curvature ahead from map. In fact, upstream code already calculates curvature from three points on the route. Using that, MTSC could provide “map\_curvature” (e.g., 1/R where R is turn radius).
   * By having both `vision_curvature` and `map_curvature`, we can feed either into a unified speed calculation formula.

3. **Unified turn speed formula:** Create a common function or class (e.g., `TurnSpeedController`) that takes curvature (and perhaps current speed) and returns a recommended max speed for that curvature. This logic might look like:

   * `v_turn = sqrt((max_lat_accel) / curvature)` – where `max_lat_accel` is a comfort lateral acceleration (we saw FrogPilot uses \~1.9 m/s² as default). This formula comes from centripetal force = v² \* curvature.
   * Aggressiveness factor: Both MTSC and VTSC have a user-configurable aggressiveness (higher = faster turns). Implement this as a multiplier on `max_lat_accel` or on the final speed. For example, an aggressiveness slider could effectively tune the allowed lateral acceleration. Ensure the unified controller can apply the same parameter whether the curve is from map or vision.
   * Smoothing: Both controllers have “UI smoothing” toggles (which just affect display) and possibly internal smoothing to avoid oscillating requests. The unified logic can include a rate limit or gradual approach to the target speed so that when a curve is detected, the speed target transitions smoothly rather than suddenly dropping. Re-use whichever method was better between MTSC and VTSC. (If MTSC had a hard cap on speed change that FrogPilot planned to remove, we likely can remove it if mapd data is reliable. VTSC probably doesn’t have a cap but is inherently limited by model seeing the curve only a short time before.)
   * Failsafe conditions: Decide if we still need the “Model Curvature Detection Failsafe” for map data. If mapd v1.9.0 has reduced false positives, we might make this failsafe default-off or remove it. The unified controller could instead choose the lower of map and vision recommended speeds if both are available, implicitly preventing false slowdowns (since if vision sees no curve, its recommended speed would be very high or no limit, and we might trust that if map’s suggestion seems anomalous). This approach could naturally filter out false positives without a hard toggle.

4. **Refactor implementation:**

   * **Step 4A: Create common helpers:** Write functions like `compute_turn_speed_from_curvature(curvature, aggressiveness)` that implements the formula and limits. Also perhaps a helper to get curvature from map data (using the points in `MapTargetVelocities`) and from vision (using model data). We can place these in a shared module (e.g., `controls/lib/turn_speed.py` or integrate into an existing planner).
   * **Step 4B: Use common logic in both controllers:** Initially, to avoid breaking everything at once, we can call the common function from within both MTSC and VTSC code paths. For example, MTSC currently computes target speed by scanning through `MapTargetVelocities` and picking a min velocity. Instead, we could compute map curvature for the sharpest upcoming turn and then get a target speed from curvature. However, to maintain exact behavior, we might do this gradually: verify that the curvature-derived speed matches the prior method’s output. During this transitional stage, keep the existing logic but log both results to compare. Once we’re confident, we can simplify MTSC to just use the curvature method. The same goes for VTSC: it might already implicitly do something similar (model likely outputs polynomial that the planner might use).
   * **Step 4C: Merge classes if appropriate:** Ultimately, we might combine `chauffeur_mtsc.py` and `chauffeur_vtsc.py` into one `turn_speed_controller.py`. This unified controller would:

     * Subscribe/get data from both mapd and model.
     * Decide which source to use (or to use both). A strategy could be: if navigation map data is available for the road ahead, use map curvature (more far-seeing); otherwise, fall back to vision curvature. Or use whichever signals a lower safe speed (for safety-first approach).
     * Contain the logic to compute the final target speed and provide it to the planner.
   * **Step 4D: Unify configuration toggles:** Combine the user-facing toggles for MTSC and VTSC into one set if possible. For example, instead of separate aggressiveness toggles, have one “Turn Speed Aggressiveness” that applies to both (since under the hood it’s one algorithm). Ensure that the UI and parameter storage is updated accordingly (this might involve a minor migration of params). Keep in mind some users may want to disable one or the other; you can implement a mode selection (e.g. “Use Map Data for curves” on/off). But ideally, the unified controller can handle both simultaneously and it decides based on data availability.

5. **Test the unified controller thoroughly (see Phase 5 for test scenarios).** Because this is a significant change, it’s wise to test in increments:

   * First, verify that using curvature calculation for MTSC still achieves the same behavior as before on known curves.
   * Then test that VTSC’s behavior is unchanged when no map data is present.
   * Finally, test scenarios where both map and vision would trigger (e.g., driving with nav on, both systems see the curve) and see that the unified logic doesn’t conflict or oscillate. If using the minimum of the two speeds, it should simply choose the slower recommendation consistently.

Unifying the controllers will greatly simplify maintenance: one code path for handling turns. It ensures consistency (e.g., the car responds to curves similarly whether detected via vision or map). It will also set the stage for future enhancements, like blending both inputs for extra safety.

Throughout this unification, maintain **implementation detail where critical** – e.g., exact parameter names, formulas, and thresholds – so that a future developer or AI agent can clearly follow the plan. At the same time, we allow for creative flexibility: the unified controller’s internal design can be adjusted (maybe an AI finds a better way to blend map and vision data) as long as the inputs/outputs remain consistent.

## Phase 5: Testing and Validation

Given the scope of changes (removing a subsystem, re-integrating another, and refactoring core control logic), comprehensive testing is essential. We should use both real-world driving and offline simulations/log replays to validate the behavior:

* **Basic functionality tests:** First ensure the car drives without errors:

  * No crashes on startup (verify that removing `mapd_py` didn’t break imports, and that the new `mapd` process launches correctly).
  * Drive on a straightforward road with no sharp turns: the car should behave as normal, with MTSC/VTSC not unnecessarily restricting speed. This checks that the default target speeds are basically “no slowdown” when not needed.
  * Engage and disengage cruise to make sure the presence of the mapd process doesn’t interfere with anything (it shouldn’t, but ensure no new alerts like “process not running” appear for mapd).

* **Scenario: Map-only curve detection** – Find a scenario with a gentle, long sweeper curve that is **beyond the model’s vision range** but present in map data:

  * Example: a highway that turns sharply after a hill or an exit ramp with known curvature. With navigation route set (or offline map loaded), approach this curve. Expected: MTSC should begin to slow the car *before* the vision model would (since the model might only “see” the curve once it’s close). The onroad UI (if MTSC status is shown) should indicate a slowdown request. The car should smoothly reduce speed to the target by the time it enters the curve.
  * If “Model Curvature Failsafe” is on, ensure the model does eventually see the curve so MTSC engages. If the failsafe prevented MTSC from activating (model didn’t flag it early), consider this a success scenario for turning that failsafe off. We want to trust map data here; gather logs to confirm mapd had a valid curve that we ignored due to the failsafe. This will support removing that toggle as upstream intended.

* **Scenario: Vision-only curve detection** – A tight turn that **is not in map data**:

  * E.g., a backroad or parking lot bend where we have no nav info. VTSC should handle it. Drive into such curves and see that VTSC (the unified controller using vision curvature) slows the car appropriately. Compare behavior to before the changes to ensure we didn’t regress vision-based slowing. If anything, with unification, VTSC might behave slightly differently; ensure any differences are acceptable (e.g., if previously VTSC had a different aggressiveness scaling, verify the new aggressiveness setting yields similar feel).
  * Also test with MTSC disabled (if we keep an enable toggle) to isolate VTSC.

* **Scenario: Combined input (redundant)** – When both map and vision are available and agree:

  * On a typical curvy road with navigation set, both systems will detect the need to slow. The unified controller should not overreact or oscillate. If we choose the lower of two speeds, we expect map usually gives early, possibly more conservative heads-up, and vision confirms later. The car should start slowing early (due to map) and the model will only reinforce that (its own suggested speed might kick in later but by then the car is already slowing).
  * Check for any ping-pong: e.g., if map suggests slowing for a curve that the model then sees as not so severe, do we risk the unified logic canceling the slowdown too soon? Ideally, once we commit to slowing (due to map), we shouldn’t speed up again just because vision says it wasn’t that bad – that could feel jerky. Our unified logic should probably take the minimum (most cautious) speed. Testing will confirm this strategy yields a smooth deceleration and re-acceleration pattern.

* **Scenario: Discrepant inputs (potential false positive)** – Cases where map data might be misleading:

  * For example, a highway overpass: map data might show a curve (for the ramp passing above) near your path even though your road stays straight. The model sees no curve, but map could erroneously suggest one. Our earlier failsafe or unified logic should handle this. Drive on a straight road segment where map has a nearby curved road. If our unified controller is set to require vision confirmation for map (failsafe on), then nothing should happen – the car will not slow on the straight (desired outcome). If failsafe is off and we rely on logic of taking min speed, then map might try to slow us. Observe if that happens:

    * If yes, that’s a false positive decel – we should address it by enabling the model-check in such edge cases or improving mapd’s filtering (perhaps mapd itself marks whether the curve is on the current route or just nearby; ensure we only use data for the active route).
    * If no false slowdowns occur, that means mapd likely only provided data for the road we’re on, or the unified logic correctly ignored it. This is good and should be verified by examining the logs (check what `MapTargetVelocities` was in that area, and if any low velocities were present that we ignored due to no vision corroboration).

* **Performance and stability tests:** Running both mapd and the unified controller should not overload the system:

  * CPU usage: The mapd process (Go binary) should be lightweight (pfeiferj’s mapd is known to run efficiently in the background). Confirm that CPU and memory usage are within limits.
  * No memory leaks or growing CPU over time – let the system run for an hour drive and ensure `mapd` remains stable (no restarts, no resource hogging).
  * When no navigation is active, mapd might still run. Check that it doesn’t consume data or battery unnecessarily. If needed, we could consider only running mapd when needed (but FrogPilot runs it always and it’s fine).

* **Unit tests or simulation harness:** If possible, create a script to simulate the controllers:

  * Feed a synthetic `MapTargetVelocities` list into the MTSC logic offline. For example, construct a scenario: current speed 30 m/s, and in 500 m there’s a curve requiring 15 m/s. Run the MTSC `target_speed` calculation and ensure it returns \~15 m/s as the target (and that it would do so at \~500 m distance out). We can vary the distance to see if it would catch it in time.
  * Similarly, feed a sequence of model curvature values (e.g., model predicts road curvature increasing) into a VTSC function to ensure it starts dropping the target speed when curvature passes a threshold. This can be done by simulating model outputs with an increasing curvature and verifying the output speed from the unified formula matches expectations (inversely proportional to sqrt of curvature).
  * If we had log data from before, replay it through the new code. Compare the commanded speeds in identical situations to ensure no unexpected behavior changes (unless desired).

* **Regression tests on straight roads and high-speed scenarios:** Ensure that on highways or straight stretches, neither controller unnecessarily limits speed. The car should be able to reach the set cruise speed. Check that `mtsc_target`/`vtsc_target` variables remain at or above the cruise speed in such cases (in code, we clamp them to not exceed the set speed). This confirms that the controllers only activate when needed and otherwise stay transparent.

Throughout testing, collect logs and record any issues. If problems arise, iterate on the implementation:

* Minor tuning (adjust aggressiveness default, tweak how early we add the 3 s lead time for braking, etc.) might be needed to make the behavior feel natural.
* Pay special attention to user comfort: the unification should not cause jarring decels. If we notice oscillation (speed goes down then up quickly), implement hysteresis: e.g., once a slowdown is initiated, perhaps require a higher threshold to cancel it.

Finally, update documentation (code comments or README) to reflect the new unified approach and how to configure it. This will help future developers or AI assistants understand the system.

## Phase 6: Future Enhancements and AI Assistance Considerations

With the system refactored, we should prepare for future development – potentially with the help of agentic AI coding assistants – by making the code and roadmap adaptable:

* **Document the interfaces clearly:** Ensure that the inputs/outputs of the unified Turn Speed Controller are well-defined (e.g., functions docstring for `update_curvature(map_curv, vision_curv) -> target_speed`). This clarity will help an AI or new developer safely modify internals without breaking the contract with other parts of the code.

* **Allow creative improvements:** The unified controller can be a foundation for more advanced logic. For instance, an AI assistant in the future might implement machine learning to predict optimal turn speed based on driver preference or use map topology (e.g., upcoming downhill vs uphill). Our roadmap should not hard-code decisions that preclude such enhancements. We’ve chosen a straightforward physical approach now, but the architecture (separating data acquisition from decision logic) allows experimentation. We explicitly mention that the curvature input is a black box – so if one wanted to fuse map and vision (e.g., take map curvature for far range and vision for near range), the structure supports plugging that in.

* **Modularity:** After unification, ensure the Turn Speed Controller is modular (maybe as its own class or module) and loosely coupled. For example, it should expose methods to receive new map data or vision data, so that testing and future modifications (maybe using different map sources or different model outputs) can be done in isolation. If an AI tool is auto-coding, a modular design makes it easier to replace one component (like the curvature calculation) without side effects.

* **Continuous validation:** Implement monitors or logs that flag unusual behavior. For example, if the unified controller requests a huge slowdown that is then quickly removed, log that as a potential false positive. These could later be turned into automated alerts or triggers for AI to analyze and improve the logic. Basically, instrument the code to gather metrics on how often and how effective the turn controller is (did we still enter turns too fast? Did we slow down too much unnecessarily?). This data-driven approach will guide further tuning.

* **User feedback and toggles:** For the time being, keep some developer toggles (like a debug mode to switch back to separate MTSC/VTSC or to disable mapd) in case things go wrong. This provides a fallback while we build confidence in the unified system. Over time, and especially if tests and users confirm the unified controller works flawlessly, these can be removed or hidden. In FrogPilot’s timeline, they planned to remove certain toggles once mapd was proven, and we can do similarly.

In conclusion, this roadmap provides a comprehensive path from removing the experimental `mapd_py` and protobuf subsystem, through re-integrating the robust upstream mapd, to gradually unifying the turn speed controllers. Each phase should be executed in order, as they build on one another. By Phase 5, we expect to have a single, reliable Turn Speed Controller that enhances safety by using map data for long-range curve awareness and vision for immediate situational awareness, all without the maintenance burden of duplicated logic or brittle proto interfaces.

Throughout the process, maintaining clear structure and documentation will enable both human developers and AI assistants to follow the plan. This ensures that future contributions – whether via automated tools or community input – can further refine the turn control system with minimal friction, ultimately leading to a smoother and smarter driving experience.
