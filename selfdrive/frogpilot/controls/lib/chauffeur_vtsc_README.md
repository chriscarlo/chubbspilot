# Steering Torque Saturation Prediction System

## Quick Reference Commands

```bash
# Run the torque analyzer to see performance statistics
python selfdrive/frogpilot/controls/lib/torque_analyzer.py --verbose

# Generate visualization plots of torque data
python selfdrive/frogpilot/controls/lib/torque_analyzer.py --plot

# Analyze data from a specific time period (e.g., last 3 days)
python selfdrive/frogpilot/controls/lib/torque_analyzer.py --days=3 --plot --verbose

# View saved model parameters
cat /data/openpilot/selfdrive/frogpilot/model_weights/torque_predictor.pkl

# View generated reports
ls -la /data/openpilot/selfdrive/frogpilot/reporting/
```

## Overview

The Steering Torque Saturation Prediction System is an advanced feature integrated into the Vision Turn Speed Controller (VTSC) that predicts and prevents steering torque saturation during turns. This system is specifically tuned for the 2023 Kia EV6 with CANFD and HDA2 hardware.

Torque saturation occurs when the steering system reaches its maximum available torque, causing the vehicle to understeer in tight turns. This system proactively reduces speed before entering curves where torque saturation would occur, resulting in smoother, more predictable, and confident cornering.

## System Architecture

The system consists of three main components:

1. **SteeringTorqueSaturationPredictor**
   This class estimates the required steering torque based on road curvature, vehicle speed, and road bank angle using a physics-based model. Key innovations include:
   - A clearly defined scale factor (`MODEL_SCALE_FACTOR = 0.01`) for unit consistency.
   - A learning system that continuously updates a sensitivity factor using an exponential moving average (EMA) of torque prediction errors.
   - Continuous logistic transition functions that smooth timing parameters (such as early approach time, spool time, and horizon factors) to avoid hard thresholds.
   - Passive mode operation that gradually transitions to active mode after detecting saturation events.
   - Driver intervention learning that rapidly adapts to driver corrections.

2. **Integration with VTSC**
   The predictor is tightly integrated into the VTSC's speed planning routine. For each point in the predicted path:
   - The baseline lateral acceleration limit is computed.
   - The required steering torque is estimated, taking into account both lateral acceleration and gravitational effects from road bank.
   - If the predicted torque exceeds the available torque, a torque-limited speed is computed and applied.
   - A confidence-based adjustment is continuously applied to the speed recommendation.

3. **Torque Analyzer**
   A utility script that collects and visualizes data. It provides statistical analysis and detailed plots to help fine-tune the prediction model based on:
   - The distribution of torque-limiting events.
   - The correlation between curvature, speed, and torque requirements.
   - The evolution of the sensitivity factor and confidence metrics over time.

## How It Works

### 1. Lateral Acceleration

The system uses a nonlinear lateral acceleration function that allows:
- Lower lateral acceleration (~1.4 m/s²) at low speeds for conservative cornering
- Higher lateral acceleration (up to ~3.2 m/s²) at highway speeds
- Smooth logistic transition between these values centered around 30 mph
- Adjustable turn aggressiveness via a multiplier

### 2. Torque Prediction

The system uses a physics-based model to estimate the steering torque required for a curve:

```
required_torque = (lateral_acceleration - g*sin(bank)) * vehicle_mass * steering_ratio * MODEL_SCALE_FACTOR * sensitivity_factor
```

Where:
- `lateral_acceleration = speed² * curvature`
- `g*sin(bank)` accounts for gravitational effects from road banking
- `MODEL_SCALE_FACTOR` (default 0.01) clarifies the scaling of the model
- `sensitivity_factor` is dynamically learned from real-world data via a continuous, EMA-based update

### 3. Available Torque Estimation

The system now **assumes a constant maximum available steering torque of 409 raw units** regardless of speed. A configurable safety margin is applied:

```
available_torque = 409 * TORQUE_MARGIN
```

The system starts in passive mode with TORQUE_MARGIN = 1.0 (no margin) and transitions to active mode (TORQUE_MARGIN = 1.0) after detecting saturation events.

### 4. Speed Limitation

When the predicted required torque exceeds the available torque, a reduced (torque-limited) speed is calculated:

```
limited_speed = sqrt((available_torque / (mass * steering_ratio * MODEL_SCALE_FACTOR * sensitivity_factor) + g * sin(road_bank)) / curvature)
```

This formula accounts for road bank effects (via the gravitational component) and ensures that the vehicle's steering remains within safe operational limits.

### 5. Learning System

The predictor continuously learns from actual steering torque measurements:
- **Error Comparison**: It compares the predicted torque with the actual measured torque.
- **EMA Smoothing**: An exponential moving average of the torque error is maintained to smooth out noise.
- **Sensitivity Adjustment**: The sensitivity factor is updated continuously based on the normalized EMA error.
- **Confidence Update**: A confidence parameter is also dynamically adjusted, influencing speed recommendations to be more conservative when uncertainty is high.
- **Calibration Phase**: Uses higher learning rates for the first 100 samples to adapt quickly.
- **Driver Intervention Learning**: Applies stronger updates when the driver intervenes with steering, gas, or brake inputs.
- **Data Persistence**: Learned parameters and recent sample data are periodically saved for offline analysis and subsequent runs.

### 6. Continuous Transition Functions

To ensure smooth behavior without abrupt threshold changes, the system uses logistic transition functions for:
- **Early Approach Time**: Smoothly varying the time to approach apex speeds (2.0s at ~8 m/s to 3.0s at ~22 m/s).
- **Early Spool Time**: Gradually ramping up speed after the apex (1.0s at ~8 m/s to 2.0s at ~22 m/s).
- **Short Horizon Factor**: Adjusting speed spooling based on the prediction horizon (from ~0.4 at horizon=1.5s up to ~1.0 at horizon=4.0s).
- **Margin Time Function**: Time-based margin that increases with speed (1.5s at 0 m/s to 5.5s at 31.3 m/s).
- **Dynamic Decel/Accel/Jerk Scales**: Speed-dependent scaling for deceleration, acceleration, and jerk limits.

These continuous functions help maintain fluid speed transitions under varying driving conditions.

## Implementation Details

### Vehicle-Specific Parameters

Configured for the Kia EV6:
- **Mass**: 2055 kg
- **Wheelbase**: 2.9 meters
- **Steering Ratio**: 16.0
- **Max Steering Torque**: 409 (raw value)

### Passive Mode Operation

The system now implements a passive learning mode:
- Starts in passive mode (TORQUE_MARGIN = 1.0) with no speed limiting
- Collects data and learns the sensitivity factor without affecting driving
- Transitions to active mode (maintaining TORQUE_MARGIN = 1.0) after detecting saturation events
- Gradually increases confidence as more data is collected

### Driver Intervention Learning

The system rapidly adapts when the driver intervenes:
- Detects steering overrides and uses them as strong learning signals
- Interprets gas pedal presses as indication that speed should be higher
- Interprets brake pedal presses as indication that speed should be lower
- Uses higher learning rates and EMA alpha values for intervention events
- Immediately exits passive mode when driver interventions occur

### Dynamic Scaling Functions

Several dynamic scaling functions adjust behavior based on speed:
- **Dynamic Decel Scale**: Transitions from 8.0 at 5m/s to 2.0 at 25m/s using a polynomial
- **Dynamic Accel Scale**: Based on decel scale with additional multipliers for low speeds
- **Dynamic Jerk Scale**: Consistent with decel scale for smooth transitions

### Integration with VTSC

Within the VTSC's `_plan_speed_trajectory` method, the following steps occur:
1. **Baseline Calculation**: Compute the standard lateral acceleration limit using a nonlinear function.
2. **Torque Estimation**: Use the predictor to estimate required torque, considering both lateral acceleration and road banking.
3. **Torque Limiting**: If the required torque exceeds available limits, a torque-limited speed is applied.
4. **Apex Detection**: Identify peaks in curvature to plan appropriate entry and exit speeds.
5. **Smoothing and Passes**: The speed profile is refined through backward/forward smoothing passes and an emergency braking check.

### Telemetry and Logging

The system logs key data points including:
- Curvature, speed, and road bank values.
- Predicted versus available torque.
- Triggered torque limitation events.
- Updates to sensitivity and confidence parameters.
- Road banking statistics.
These logs are stored in the standard openpilot log files and can be examined using the `torque_analyzer.py` script.

### Data Storage

Learned model parameters are stored in:

```
selfdrive/frogpilot/model_weights/torque_predictor.pkl
```

Analysis reports and visualizations are saved to:

```
/data/openpilot/selfdrive/frogpilot/reporting/
```

## Advanced Features

### 1. Learning Capability

- **Continuous Learning**: The system updates the sensitivity factor using an EMA of torque errors, ensuring gradual and robust adaptation.
- **Adaptive Confidence**: A continuously adjusted confidence parameter helps modulate speed recommendations under uncertainty.
- **Calibration Phase**: Uses higher learning rates for initial samples to adapt quickly.
- **Driver Intervention Learning**: Applies stronger updates when the driver intervenes.
- **Persistent Data**: Periodic saving of learned parameters ensures consistent performance across sessions.

### 2. Continuous Transition Functions

All key timing functions (early approach, early spool, and horizon scaling) use logistic transitions, providing smooth, continuous adjustments rather than hard breakpoints.

### 3. Apex Detection and Handling

The system identifies "apexes" (peaks in curvature) and applies special handling:
- Earlier deceleration approaching the apex
- Holding the apex speed through the tightest part of the curve
- Smooth acceleration out of the apex
- Adjustments based on the prediction horizon length

## Tuning Parameters

The system exposes several parameters for tuning:
- **TORQUE_MARGIN**: Safety margin applied to available torque (default: 1.0 in both passive and active modes)
- **learning_rate**: Determines how quickly the sensitivity factor is updated (default: 0.02, 0.10 during calibration)
- **ema_alpha**: Smoothing factor for error (default: 0.01, 0.05 during calibration)
- **sensitivity_factor**: Initial sensitivity of the model (default: 2.0)
- **confidence**: Initial confidence level of the model (default: 0.5)
- **MODEL_SCALE_FACTOR**: Scaling constant in the torque prediction (default: 0.01)
- **saturation_threshold_pct**: Percentage of max torque considered as saturation (default: 0.95)

These parameters can be adjusted within the `SteeringTorqueSaturationPredictor` class to optimize performance.

## Troubleshooting

### Common Issues

1. **Excessive Speed Reduction**
   - If the system reduces speed too aggressively, the sensitivity factor may be over-adjusting.
   - Check analyzer outputs for average sensitivity values and adjust the learning rate if necessary.

2. **Insufficient Speed Reduction (Torque Saturation Occurs)**
   - A low sensitivity factor might be insufficient to trigger necessary speed reductions.
   - Verify torque measurements and ensure that vehicle parameters (mass, steering ratio) are correct.

3. **Model Not Learning**
   - Ensure the model_weights directory exists and is writable.
   - Check logs for errors during model saving/loading.
   - Confirm that steering torque data is being captured accurately.

4. **System Remains in Passive Mode**
   - The system may not have detected saturation events yet.
   - Check the saturation_threshold_pct value (default 0.95).
   - Manually trigger driver intervention learning by applying steering input in curves.

### Monitoring Performance

Regularly run the torque analyzer to review:
- The percentage and distribution of torque-limiting events.
- Current sensitivity and confidence values.
- The relationship between curvature, speed, and torque requirements.
- Road banking statistics and their effect on torque requirements.

## Technical Notes for Developers

### Code Structure

- **Lateral Acceleration Functions**: Nonlinear functions for determining safe lateral acceleration limits.
- **Apex Detection**: Logic for identifying peaks in curvature for special handling.
- **Dynamic Scaling Functions**: Speed-dependent scaling for deceleration, acceleration, and jerk.
- **Transition Functions**: Logistic functions for smooth parameter transitions.
- **SteeringTorqueSaturationPredictor**: Handles torque prediction, continuous learning, and data persistence.
- **VisionTurnSpeedController**: Main class that integrates all components for speed planning.

### Dependencies

The system uses standard Python libraries available in the openpilot environment:
- `numpy`
- `pickle`
- `collections.deque`
- `time`
- `os`
- `math`
- `cereal.messaging`
- `common.conversions`
- `common.numpy_fast`
- `common.params`
- `common.swaglog`
- `selfdrive.controls.lib.drive_helpers`
- `selfdrive.modeld.constants`

### Extending the System

To adapt this system to other vehicles:
1. Update vehicle parameters (mass, wheelbase, steering ratio).
2. Adjust the torque prediction model for different steering characteristics.
3. Modify available torque computations if necessary.
4. Consider additional factors such as tire grip and suspension dynamics.

## Future Improvements

Potential enhancements include:
1. Incorporating road surface conditions (e.g., wet/dry).
2. Factoring in vehicle loading (passengers, cargo) into the model.
3. Integrating vision model confidence for more adaptive speed planning.
4. Developing a more sophisticated torque model based on additional data.
5. Adding tire grip limits alongside steering torque considerations.
6. Enhancing the driver intervention learning with more nuanced interpretations of driver inputs.
7. Improving road banking compensation with more detailed mapping data.

---

This updated system leverages continuous functions, adaptive learning mechanisms, and a sophisticated torque prediction model to deliver refined and predictable steering performance. The result is smoother, safer cornering and improved handling of torque limitations.