# Phase 3: Adapt `mapd` Output for MTSC Compatibility

Now that the original mapd is in place, we ensure that its outputs line up exactly with what the MTSC code expects, making adjustments either in mapd's data publication or in MTSC's input handling:

## 1. Ensure param keys and format match
The MTSC controller in our code likely expects map data via shared params. From the existing MTSC logic (in `chauffeur_mtsc.py` or similar), we see it reads JSON from keys `"LastGPSPosition"` and `"MapTargetVelocities"`. We must confirm that our mapd process writes those exact keys in the same JSON structure:

* `LastGPSPosition`: typically a JSON object like `{"latitude": ..., "longitude": ...}`. If mapd uses a different key or format for current position, adapt it. (Given both FrogPilot and our code refer to `LastGPSPosition`, this is likely consistent).
* `MapTargetVelocities`: expected to be a JSON array of points, where each point has at least `latitude`, `longitude`, and a `velocity`. Our MTSC code iterates over this list. Check the actual output of mapd: if the keys differ (e.g. `speed` instead of `velocity`) or units differ (m/s vs MPH), we need to handle that. In FrogPilot's case, they likely use m/s for velocity in this structure. We should verify (e.g. by checking pfeiferj's documentation or printing a sample of `MapTargetVelocities` at runtime).

## 2. Adapt mapd process if needed
If we discover any mismatch, prefer to adjust in the mapd wrapper:

* For example, if the mapd binary writes a different param name or format (though unlikely, since FrogPilot's MTSC is working with it), we can add a small translator. Since the `mapd` process is written to always run, one approach is to modify the Python wrapper to normalize the output. However, since the binary likely writes directly to params, intercepting that might not be trivial. A better approach is to configure mapd via its inputs or settings to use the expected output. If pfeiferj's mapd has flags or config (perhaps via a capnp/JSON toggle) to enable the FrogPilot-style output, ensure that's enabled.
* If absolutely required, a lightweight solution is to have a small Python loop (maybe as part of `frogpilot_process`) that watches for mapd's output (like a different param or file) and copies it into `MapTargetVelocities` in the expected format. This is a fallback; ideally we won't need this if versions align.

## 3. Simplify MTSC code (if needed)
Our existing MTSC (chauffeur_mtsc.py) might contain extra logic due to the previous `mapd_py` implementation. For instance, it might have been constructing proto messages or waiting on a protobuf signal. Now that we revert to the param approach, clean up MTSC:

* Remove any code dealing with proto deserialization. Instead, ensure it reads from the params like FrogPilot's does. If our MTSC was already modeled on FrogPilot's, it may already do this reading (or we can replace it with FrogPilot's MTSC logic as a reference).
* Verify the MTSC toggle. FrogPilot has a param "MTSCEnabled" (likely we do too). Ensure this still controls whether MTSC runs. If previously `mapd_py` used a different flag, unify it to the standard one.
* Check how MTSC determines "curve ahead". In FrogPilot's MTSC, after reading target velocities, it calculates whether a slower speed is needed and returns a target speed. Our MTSC should now behave the same. If there were any differences (say, `mapd_py` had additional criteria), consider removing them to match the simpler logic.
* One known difference: if `mapd_py` used protobuf messages, MTSC might have waited for a message on a socket rather than continuously polling params. With the param method, MTSC can be called every planner cycle (the code likely already does this in the planner update). Ensure that the planner or control loop is invoking MTSC's `target_speed()` regularly (this should already be true, as in FrogPilot's `frogpilot_planner.py` it calls `mtsc.target_speed(...)` each cycle).

## 4. Verify end-to-end data flow
With mapd running and MTSC consuming, test on a bench or device:

* Simulate or run the car with a navigation route (or on a road with offline map data) and print out MTSC's computed `mtsc_target`. It should go from 0 (or cruise speed) down to some value when approaching a curve.
* Log the content of `MapTargetVelocities` to ensure it contains plausible upcoming speeds. For example, on a highway, many entries might have `velocity` equal to the speed limit, and on a tight upcoming turn, an entry might have a lower `velocity` (indicating slow down).
* Confirm that MTSC picks up the lowest needed speed. If something's off (say, no slowdowns trigger), we may need to adjust how far ahead mapd provides data or the threshold in MTSC.
* If the car has no navigation route set, test if mapd still produces data for the current road. Ideally, it should (using the current road's geometry), enabling MTSC on "random drive" without a destination. If it doesn't, note that MTSC will effectively be idle when not navigating. (This could be acceptable, but FrogPilot's offline maps likely means it *does* always have data from OSM.)

## Success Criteria
By completing Phase 3, the original mapd and the MTSC consumer should work in tandem. We will have effectively swapped out the internals of MTSC's data source without the rest of the control stack noticing a difference (except improved reliability). MTSC will directly use mapd's outputs (via shared params) as it did in upstream FrogPilot. The protobuf-based communication channel is gone, simplifying the system.