# Phase 5: Testing and Validation

Given the scope of changes (removing a subsystem, re-integrating another, and refactoring core control logic), comprehensive testing is essential. We should use both real-world driving and offline simulations/log replays to validate the behavior:

## Basic functionality tests
First ensure the car drives without errors:

* No crashes on startup (verify that removing `mapd_py` didn't break imports, and that the new `mapd` process launches correctly).
* Drive on a straightforward road with no sharp turns: the car should behave as normal, with MTSC/VTSC not unnecessarily restricting speed. This checks that the default target speeds are basically "no slowdown" when not needed.
* Engage and disengage cruise to make sure the presence of the mapd process doesn't interfere with anything (it shouldn't, but ensure no new alerts like "process not running" appear for mapd).

## Scenario: Map-only curve detection
Find a scenario with a gentle, long sweeper curve that is **beyond the model's vision range** but present in map data:

* Example: a highway that turns sharply after a hill or an exit ramp with known curvature. With navigation route set (or offline map loaded), approach this curve. Expected: MTSC should begin to slow the car *before* the vision model would (since the model might only "see" the curve once it's close). The onroad UI (if MTSC status is shown) should indicate a slowdown request. The car should smoothly reduce speed to the target by the time it enters the curve.
* If "Model Curvature Failsafe" is on, ensure the model does eventually see the curve so MTSC engages. If the failsafe prevented MTSC from activating (model didn't flag it early), consider this a success scenario for turning that failsafe off. We want to trust map data here; gather logs to confirm mapd had a valid curve that we ignored due to the failsafe. This will support removing that toggle as upstream intended.

## Scenario: Vision-only curve detection
A tight turn that **is not in map data**:

* E.g., a backroad or parking lot bend where we have no nav info. VTSC should handle it. Drive into such curves and see that VTSC (the unified controller using vision curvature) slows the car appropriately. Compare behavior to before the changes to ensure we didn't regress vision-based slowing. If anything, with unification, VTSC might behave slightly differently; ensure any differences are acceptable (e.g., if previously VTSC had a different aggressiveness scaling, verify the new aggressiveness setting yields similar feel).
* Also test with MTSC disabled (if we keep an enable toggle) to isolate VTSC.

## Scenario: Combined input (redundant)
When both map and vision are available and agree:

* On a typical curvy road with navigation set, both systems will detect the need to slow. The unified controller should not overreact or oscillate. If we choose the lower of two speeds, we expect map usually gives early, possibly more conservative heads-up, and vision confirms later. The car should start slowing early (due to map) and the model will only reinforce that (its own suggested speed might kick in later but by then the car is already slowing).
* Check for any ping-pong: e.g., if map suggests slowing for a curve that the model then sees as not so severe, do we risk the unified logic canceling the slowdown too soon? Ideally, once we commit to slowing (due to map), we shouldn't speed up again just because vision says it wasn't that bad – that could feel jerky. Our unified logic should probably take the minimum (most cautious) speed. Testing will confirm this strategy yields a smooth deceleration and re-acceleration pattern.

## Scenario: Discrepant inputs (potential false positive)
Cases where map data might be misleading:

* For example, a highway overpass: map data might show a curve (for the ramp passing above) near your path even though your road stays straight. The model sees no curve, but map could erroneously suggest one. Our earlier failsafe or unified logic should handle this. Drive on a straight road segment where map has a nearby curved road. If our unified controller is set to require vision confirmation for map (failsafe on), then nothing should happen – the car will not slow on the straight (desired outcome). If failsafe is off and we rely on logic of taking min speed, then map might try to slow us. Observe if that happens:
  * If yes, that's a false positive decel – we should address it by enabling the model-check in such edge cases or improving mapd's filtering (perhaps mapd itself marks whether the curve is on the current route or just nearby; ensure we only use data for the active route).
  * If no false slowdowns occur, that means mapd likely only provided data for the road we're on, or the unified logic correctly ignored it. This is good and should be verified by examining the logs (check what `MapTargetVelocities` was in that area, and if any low velocities were present that we ignored due to no vision corroboration).

## Performance and stability tests
Running both mapd and the unified controller should not overload the system:

* **CPU usage**: The mapd process (Go binary) should be lightweight (pfeiferj's mapd is known to run efficiently in the background). Confirm that CPU and memory usage are within limits.
* **No memory leaks or growing CPU over time** – let the system run for an hour drive and ensure `mapd` remains stable (no restarts, no resource hogging).
* When no navigation is active, mapd might still run. Check that it doesn't consume data or battery unnecessarily. If needed, we could consider only running mapd when needed (but FrogPilot runs it always and it's fine).

## Unit tests or simulation harness
If possible, create a script to simulate the controllers:

* Feed a synthetic `MapTargetVelocities` list into the MTSC logic offline. For example, construct a scenario: current speed 30 m/s, and in 500 m there's a curve requiring 15 m/s. Run the MTSC `target_speed` calculation and ensure it returns ~15 m/s as the target (and that it would do so at ~500 m distance out). We can vary the distance to see if it would catch it in time.
* Similarly, feed a sequence of model curvature values (e.g., model predicts road curvature increasing) into a VTSC function to ensure it starts dropping the target speed when curvature passes a threshold. This can be done by simulating model outputs with an increasing curvature and verifying the output speed from the unified formula matches expectations (inversely proportional to sqrt of curvature).
* If we had log data from before, replay it through the new code. Compare the commanded speeds in identical situations to ensure no unexpected behavior changes (unless desired).

## Regression tests on straight roads and high-speed scenarios
Ensure that on highways or straight stretches, neither controller unnecessarily limits speed. The car should be able to reach the set cruise speed. Check that `mtsc_target`/`vtsc_target` variables remain at or above the cruise speed in such cases (in code, we clamp them to not exceed the set speed). This confirms that the controllers only activate when needed and otherwise stay transparent.

## Iteration and refinement
Throughout testing, collect logs and record any issues. If problems arise, iterate on the implementation:

* Minor tuning (adjust aggressiveness default, tweak how early we add the 3 s lead time for braking, etc.) might be needed to make the behavior feel natural.
* Pay special attention to user comfort: the unification should not cause jarring decels. If we notice oscillation (speed goes down then up quickly), implement hysteresis: e.g., once a slowdown is initiated, perhaps require a higher threshold to cancel it.

## Documentation update
Finally, update documentation (code comments or README) to reflect the new unified approach and how to configure it. This will help future developers or AI assistants understand the system.

## Success Criteria
By the end of Phase 5, we should have comprehensive test results demonstrating that:
- The basic functionality works without errors
- Map-based curve detection works as expected for far-ahead curves
- Vision-based curve detection continues to work for unmapped roads
- Combined inputs work harmoniously without oscillation
- False positives are minimized or eliminated
- System performance remains stable
- The unified controller behaves predictably across various scenarios