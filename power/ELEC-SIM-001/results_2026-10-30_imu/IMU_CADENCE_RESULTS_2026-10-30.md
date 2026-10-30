# ELEC-SIM-001 v1.5.1: IMU gait and cadence results

| Field | Value |
| --- | --- |
| Date | 2026-10-30 |
| Command | `python run_sim.py --outdir results_2026-10-30_imu --imu-archive ".../Documents/usf/exo/archive.zip"` |
| Gait model | `one_sided_battery_current.m` port, Moco hemi XML, authoritative |
| IMU input | Shimmer archive, read in place, groups G01 to G05 (folders, not people) |
| Regression | All S1 to S14 results and the v1.5 studies match the 2026-10-29 run field by field |
| Status | Preliminary. Five new parameters are ASSUMED. |

**Summary.** Pack current is nearly insensitive to walking speed. Slowing the Moco cycle from 0.836 s to the measured median of 1.26 s lowers coupled mean current by 5% at full assist (4.21 A to 3.98 A), because 59% of the bus load is motor copper loss, which depends on torque and not speed. The Moco knee angular velocity peak of 9.5 rad/s is about twice the measured 90th percentile.

## 1. Measured gait (IMU archive)

| Quantity | Value |
| --- | --- |
| Sessions used / files rejected | 89 / 1 (spreadsheet re-save, header and numbers corrupted) |
| Sessions with at least one stride | 82 |
| Strides detected | 250 |
| Stride time p10 / median / p90 | 1.091 / 1.260 / 1.433 s |
| Cadence at median | 47.6 strides/min (Moco: 71.8) |
| Median stride per group | G01 1.728 s, G02 1.315 s, G03 1.269 s, G04 1.235 s, G05 1.324 s |
| Sessions with shank gyro clipped at about 500 deg/s | 31 of 89 |
| Knee peak angular velocity, unclipped sessions (52), median / p90 | 2.2 / 4.5 rad/s |
| Knee peak angular velocity, all sessions (84, lower bound), median / p90 | 2.5 / 6.6 rad/s |
| Moco weak-knee peak angular velocity | 9.5 rad/s |

G01 walked markedly slower (1.73 s median stride, shank peak about 2 rad/s); it contributes few strides.

## 2. Cadence study (50% SOC, auxiliary load 45 W)

| Cycle time | Source | Mean A, assist 100% | Runtime, 100% | Mean A, assist 40% | Runtime, 40% |
| --- | --- | --- | --- | --- | --- |
| 0.836 s | Moco | 4.21 A | 1.07 h | 2.28 A | 1.97 h |
| 1.091 s | IMU p10 | 4.05 A | 1.11 h | 2.19 A | 2.05 h |
| 1.260 s | IMU median | 3.98 A | 1.13 h | 2.16 A | 2.09 h |
| 1.433 s | IMU p90 | 3.96 A | 1.14 h | 2.14 A | 2.11 h |
| 1.600 s | grid | 3.93 A | 1.14 h | 2.11 A | 2.13 h |

No point trips the BMS. Knee RMS phase current is unchanged by cadence (19.14 A at 100%, 11.56 A at 40%), because the moment profile is held.

Mean bus power breakdown at assist 100%:

| Cycle time | Total | Auxiliary | Mechanical | Copper loss |
| --- | --- | --- | --- | --- |
| 0.836 s | 183.2 W | 45.0 W | 29.5 W | 108.7 W |
| 1.260 s | 174.3 W | 45.0 W | 15.1 W | 114.2 W |
| 1.600 s | 171.6 W | 45.0 W | 7.3 W | 119.3 W |

Copper loss rises slightly at slower cadence because fewer samples fall into net braking, where the MATLAB model sets battery power to zero.

## 3. Assessment

1. **Cadence is a second-order effect on the pack.** The Moco cycle is a conservative but not materially pessimistic basis for battery sizing (4 to 6% high on mean current across the measured p10 to p90 stride range).
2. **Copper loss is the dominant load.** It is set by `ctl_km_Nm_per_sqrtW` (0.2387) and `ctl_hot_factor` (1.3). These two values affect runtime more than gait speed does, which raises the priority of the Km and loss-model question for Luis (run report, Section 8 item 2).
3. **The Moco knee angular velocity is high against measurement.** 9.5 rad/s exceeds the measured unclipped p90 (4.5 rad/s) and the clipped lower-bound p90 (6.6 rad/s). Since mechanical power is only 16% of the load, the battery impact is small, but the value should be checked with Luis before it is used for actuator speed sizing.
4. **The measured cohort walks slowly** (47.6 strides/min). Whether it represents the EXO target population is not established; the archive has no diagnosis or condition labels that can be relied on.

## 4. Assumptions and limits

- `cadence_torque_held` (ASSUMED): the moment profile is held as cadence changes. Measured moments fall at slower walking speed, so copper loss at slow cadence is overstated.
- Knee angular velocity uses thigh minus shank sagittal gyro, with axis signs aligned by correlation, not by a recorded mounting orientation.
- Unclipped statistics are biased toward slower walkers, because faster sessions clip.
- Provenance and consent for the archive are not on record. Keep the raw files out of any repository.
