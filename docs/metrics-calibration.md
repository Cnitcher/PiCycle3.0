# Metrics Calibration

PiCycle reports virtual machine metrics from one Hall sensor. They are intended to be
repeatable workout scores, not road-bike GPS speed or laboratory metabolic measurements.

## 2026-07-23 Baseline

Field observation: a very easy ride displayed about 20 mph, while the desired cockpit
speed was 10-12 mph.

The default settings now use:

```json
{
  "speed_distance_multiplier": 0.55,
  "sensor_pulses_per_crank_rev": 5.0
}
```

- Speed and distance use the same `0.55` scale so they remain internally consistent.
  The observed 20 mph becomes 11 mph.
- Cadence divides the Hall sensor's pulse rate by 5. This estimates crank RPM when the
  sensed fan/shaft turns five times per crank revolution.

## Echo-Style Effort

The Rogue Echo Bike reports speed, watts, cadence, and calories, but Rogue does not
publish its internal calorie formula. PiCycle therefore uses an approximation, not a
claim of exact Rogue parity.

`effort.py` converts estimated crank RPM to watts with this public V2/V3 calibration
curve:

```text
watts = 0.00001*rpm^4 - 0.0011*rpm^3 + 0.1455*rpm^2 - 3.3264*rpm + 29.355
```

Below 20 RPM, the implementation blends the 20 RPM result linearly down to zero to
avoid phantom output from the fitted curve's non-zero intercept.

Machine calories then accumulate as:

```text
calories = watts * elapsed_seconds / 1200
```

Reference points:

| Crank RPM | Approx. watts | Machine Cal/min |
| ---: | ---: | ---: |
| 0 | 0.0 | 0.0 |
| 40 | 84.3 | 4.2 |
| 50 | 151.8 | 7.6 |
| 60 | 245.6 | 12.3 |
| 70 | 372.3 | 18.6 |
| 80 | 540.8 | 27.0 |

These are machine calories: a consistent workout-output score. They do not use rider
weight and should not be presented as an individualized medical estimate of energy
expenditure.

## Field Tuning

For a new speed observation, update the multiplier proportionally:

```text
new multiplier = old multiplier * desired displayed mph / observed displayed mph
```

To validate cadence gearing, turn the crank a known number of complete revolutions,
count Hall pulses, and set `sensor_pulses_per_crank_rev` to:

```text
counted pulses / crank revolutions
```

Sources:

- Rogue Echo Bike V3 product/monitor description:
  <https://www.roguefitness.com/rogue-echo-bike>
- Public Echo V2/V3 cadence-to-watts curve:
  <https://airbike.vip/>
- Community-observed 1 calorie per roughly 1,200 watt-seconds:
  <https://www.reddit.com/r/crossfit/comments/rw53f2/new_rogue_echo_bike_calories/>
