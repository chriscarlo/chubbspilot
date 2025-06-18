# Phase 4: Unify MTSC and VTSC Logic

With a functioning Map Turn Speed Controller and Vision Turn Speed Controller (VTSC) both in place, attention turns to unifying these into a single Turn Speed Controller logic. The long-term goal is one controller that uses curvature input from either maps or vision as available. Achieving full unification will likely be iterative:

## 1. Compare current implementations
Start by reviewing `chauffeur_mtsc.py` and `chauffeur_vtsc.py` side-by-side. Document what each is doing:

* How does VTSC determine a curve and target speed? (Likely using model path curvature or lane curvature from the model outputs.)
* How does MTSC determine target speed from map data? (Now it uses the approach restored from FrogPilot.)
* Identify differences: e.g., VTSC might have a "sensitivity" setting to decide what curvature triggers a slowdown, whereas MTSC relies on map data and had a "model curvature failsafe" toggle to avoid false positives. There may also be differences in how the target speed is smoothed or applied (VTSC might engage more gradually).
* Note any common elements: ultimately both produce a target speed (or speed limit) for the planner to use when approaching a curve.

## 2. Abstract the input – curvature as common metric
Plan a refactor where both controllers feed a common logic with a measure of curve severity. We treat curvature as the "black box" input:

* For VTSC: compute curvature from vision (the model's predicted path). In code, FrogPilot already computes `road_curvature = calculate_road_curvature(modelData, v_ego)` each cycle. Ensure we have a similar function (if not, we can adopt FrogPilot's).
* For MTSC: compute curvature from map data. The mapd output gives target speeds, but we can derive curvature as well. FrogPilot's MTSC update in v0.9.7 introduced a direct curvature calculation from map points. We should incorporate something similar so that we have an estimate of road curvature ahead from map. In fact, upstream code already calculates curvature from three points on the route. Using that, MTSC could provide "map_curvature" (e.g., 1/R where R is turn radius).
* By having both `vision_curvature` and `map_curvature`, we can feed either into a unified speed calculation formula.

## 3. Unified turn speed formula
Create a common function or class (e.g., `TurnSpeedController`) that takes curvature (and perhaps current speed) and returns a recommended max speed for that curvature. This logic might look like:

* `v_turn = sqrt((max_lat_accel) / curvature)` – where `max_lat_accel` is a comfort lateral acceleration (we saw FrogPilot uses ~1.9 m/s² as default). This formula comes from centripetal force = v² * curvature.
* **Aggressiveness factor**: Both MTSC and VTSC have a user-configurable aggressiveness (higher = faster turns). Implement this as a multiplier on `max_lat_accel` or on the final speed. For example, an aggressiveness slider could effectively tune the allowed lateral acceleration. Ensure the unified controller can apply the same parameter whether the curve is from map or vision.
* **Smoothing**: Both controllers have "UI smoothing" toggles (which just affect display) and possibly internal smoothing to avoid oscillating requests. The unified logic can include a rate limit or gradual approach to the target speed so that when a curve is detected, the speed target transitions smoothly rather than suddenly dropping. Re-use whichever method was better between MTSC and VTSC. (If MTSC had a hard cap on speed change that FrogPilot planned to remove, we likely can remove it if mapd data is reliable. VTSC probably doesn't have a cap but is inherently limited by model seeing the curve only a short time before.)
* **Failsafe conditions**: Decide if we still need the "Model Curvature Detection Failsafe" for map data. If mapd v1.9.0 has reduced false positives, we might make this failsafe default-off or remove it. The unified controller could instead choose the lower of map and vision recommended speeds if both are available, implicitly preventing false slowdowns (since if vision sees no curve, its recommended speed would be very high or no limit, and we might trust that if map's suggestion seems anomalous). This approach could naturally filter out false positives without a hard toggle.

## 4. Refactor implementation

### Step 4A: Create common helpers
Write functions like `compute_turn_speed_from_curvature(curvature, aggressiveness)` that implements the formula and limits. Also perhaps a helper to get curvature from map data (using the points in `MapTargetVelocities`) and from vision (using model data). We can place these in a shared module (e.g., `controls/lib/turn_speed.py` or integrate into an existing planner).

### Step 4B: Use common logic in both controllers
Initially, to avoid breaking everything at once, we can call the common function from within both MTSC and VTSC code paths. For example, MTSC currently computes target speed by scanning through `MapTargetVelocities` and picking a min velocity. Instead, we could compute map curvature for the sharpest upcoming turn and then get a target speed from curvature. However, to maintain exact behavior, we might do this gradually: verify that the curvature-derived speed matches the prior method's output. During this transitional stage, keep the existing logic but log both results to compare. Once we're confident, we can simplify MTSC to just use the curvature method. The same goes for VTSC: it might already implicitly do something similar (model likely outputs polynomial that the planner might use).

### Step 4C: Merge classes if appropriate
Ultimately, we might combine `chauffeur_mtsc.py` and `chauffeur_vtsc.py` into one `turn_speed_controller.py`. This unified controller would:

* Subscribe/get data from both mapd and model.
* Decide which source to use (or to use both). A strategy could be: if navigation map data is available for the road ahead, use map curvature (more far-seeing); otherwise, fall back to vision curvature. Or use whichever signals a lower safe speed (for safety-first approach).
* Contain the logic to compute the final target speed and provide it to the planner.

### Step 4D: Unify configuration toggles
Combine the user-facing toggles for MTSC and VTSC into one set if possible. For example, instead of separate aggressiveness toggles, have one "Turn Speed Aggressiveness" that applies to both (since under the hood it's one algorithm). Ensure that the UI and parameter storage is updated accordingly (this might involve a minor migration of params). Keep in mind some users may want to disable one or the other; you can implement a mode selection (e.g. "Use Map Data for curves" on/off). But ideally, the unified controller can handle both simultaneously and it decides based on data availability.

## 5. Test the unified controller thoroughly (see Phase 5 for test scenarios)
Because this is a significant change, it's wise to test in increments:

* First, verify that using curvature calculation for MTSC still achieves the same behavior as before on known curves.
* Then test that VTSC's behavior is unchanged when no map data is present.
* Finally, test scenarios where both map and vision would trigger (e.g., driving with nav on, both systems see the curve) and see that the unified logic doesn't conflict or oscillate. If using the minimum of the two speeds, it should simply choose the slower recommendation consistently.

## Success Criteria
Unifying the controllers will greatly simplify maintenance: one code path for handling turns. It ensures consistency (e.g., the car responds to curves similarly whether detected via vision or map). It will also set the stage for future enhancements, like blending both inputs for extra safety.

Throughout this unification, maintain **implementation detail where critical** – e.g., exact parameter names, formulas, and thresholds – so that a future developer or AI agent can clearly follow the plan. At the same time, we allow for creative flexibility: the unified controller's internal design can be adjusted (maybe an AI finds a better way to blend map and vision data) as long as the inputs/outputs remain consistent.