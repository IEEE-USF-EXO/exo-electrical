# ELEC-SIM-001 v1.5 Run Report

| Field | Value |
| --- | --- |
| Date | 2026-10-29 |
| Package | ELEC-SIM-001 v1.5, Kiboard Warriors (ELEC-013 to ELEC-015) |
| Load model | `one_sided_battery_current.m` (Luis, Electrical > Test Data), Python port in `sim/gaitctl.py` |
| Gait input | `PostStroke_Moco_Comparison_Data_Hemi.xml`, `gait_data_is_authoritative: true` |
| Outputs | `results_2026-10-29/ELEC-SIM-001_Results_v1.5.json`, `ELEC-SIM-001_Overview_v1.5.png`, `ELEC-SIM-001_Integration_v1.5.png` |
| Status | Preliminary. No parameter is measured on EXO hardware. 50 parameters are PROPOSED or ASSUMED and are not cleared for design use. |

**Summary.** The pack and the BMS do not limit ordinary walking at any assist level from 0 to 100%. Three issues need action before PDR sign-off: (1) a repeated 0.4 s dual-actuator surge passes under both the 1.0 s discharge-overcurrent delay and the 0.5 s undervoltage delay, and drives cells to 2.34 V at 30% SOC with no trip; (2) the knee actuator exceeds its 12 A rated RMS phase current above about 42% assist, so that is the usable assist ceiling, not the pack; (3) the 1.56 h runtime figure uses the MATLAB 48 V current with no auxiliary load and overstates runtime by roughly 30 to 45%.

---

## 1. Run configuration and reproducibility

- Command: `python run_sim.py --outdir results_2026-10-29` (all scenarios and both studies, defaults: assist 1.0, sweep at 90% SOC).
- Environment: Python 3.11, numpy 2.4.6, matplotlib 3.11.2, scipy 1.17.1 (OCV interpolation is pchip, matching `battery_ocv.m`). Wall time 90 s.
- Gait: weak side left, strong leg shifted 51.5% of the cycle, cycle 0.836 s (71.8 cycles/min).
- Port check at 48 V: peak 10.33 A, mean 2.88 A, RMS 3.68 A. These match the independent re-implementation in `RESULTS_SUMMARY_v1.5.md`.
- **Reproducibility: the results JSON is identical, field by field, to the 2026-10-22 baseline in `results/`.** No code or data drift since the last run.

The comparison against `one_sided_battery_current.m` run in MATLAB itself is still open (Section 8).

## 2. Scenario results

| ID | Scenario | Outcome | Time to trip | Peak current | Min pack V | Min cell V | Assessment |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | Nominal gait, closed loop, 95% SOC, 30 s | No trip | n/a | 11.61 A | 46.59 V | 3.887 V | Pass. Mean bus power 182.7 W. |
| S2 | 56 A dual-actuator demand on gait | DISCHARGE_OVERCURRENT | 2.001 s (surge starts 1.0 s) | 63.19 A | 37.41 V | 3.144 V | Pass. Trip at the 1.0 s OCP delay. |
| S3 | Bolted fault, 150 A | SHORT_CIRCUIT | 0.209 s (fault at 0.200 s) | 151.28 A | 19.96 V | 1.726 V | Pass. Trip at the 10 ms SC delay. |
| S4 | 10 A charge step at 95% SOC | No trip | n/a | 3.98 A accepted | 49.38 V | max 4.180 V | Pass. Overvoltage headroom limits charge to 34% acceptance; charge OCP is never reached. |
| S5 | 4.5 A charge, one cell 12% high | No trip | n/a | 4.5 A | 48.38 V | max 4.180 V | Pass. 69% acceptance, OV headroom binds. |
| S6 | Thermal ramp at 3.5 A | OVER_TEMPERATURE | 60.0 s (warn at 50.0 s) | 3.5 A | 47.56 V | 3.966 V | Pass. Trip at 55.25 C. |
| S7 | 2 s telemetry dropout during gait | No trip | n/a | 11.80 A | 45.85 V | 3.826 V | Pass. DERATE_STALE at 8.401 s, NORMAL at 10.999 s. |
| S9 | Charge at minus 5 C | CHARGE_TEMP_INHIBIT | 0.0 s | 0 A | 44.82 V | 3.735 V | Pass. |
| S10 | Dual-actuator peak once per stride, 0.4 s each, 90% SOC, 5 s | No trip | n/a | 65.12 A | 34.70 V | **2.919 V** | **Fail. See Finding 1.** |
| S11 | Regen at 98% SOC, no clamp | No trip | n/a | 11.45 A | 47.26 V | 3.943 V | Not exercised. No charge reached the pack. |
| S12 | Regen at 98% SOC, clamp fitted | No trip | n/a | 11.45 A | 47.26 V | 3.943 V | Not exercised. Clamp energy 0 Wh. |
| S13 | Gait at 12% SOC, 40 s | No trip | n/a | 10.27 A | 36.23 V | **3.020 V** | **Marginal. See Finding 2.** |
| S14 | Regen at 40% SOC | No trip | n/a | 13.19 A | 41.02 V | 3.424 V | Not exercised. No charge reached the pack. |

Proposed BMS settings referenced below (all PROPOSED in `sim/params.py`): discharge OCP 45 A, 1.0 s; short circuit 100 A, 10 ms; UVP trip 3.00 V/cell, warn 3.30 V/cell, delay 0.5 s; cell discharge cutoff 2.5 V.

## 3. Finding 1: repeated actuator surge is not caught by any protection

Each S10 surge lasts 0.4 s. That is shorter than the 1.0 s OCP delay and the 0.5 s UVP delay, and both timers reset between strides. The BMS therefore never acts, although current reaches 65 A against a 45 A cell continuous rating (RK-01) and cell voltage falls below the UVP trip on every stride.

A sensitivity run was made outside the package (scratch script, no package files changed) with S10 extended to 60 s at four SOC values and two assist levels:

| Assist | Start SOC | Outcome | Peak current | Min cell V | Max temp, 60 s |
| --- | --- | --- | --- | --- | --- |
| 1.0 | 90% | No trip | 65.12 A | 2.825 V | 46.5 C |
| 1.0 | 50% | No trip | 65.97 A | 2.521 V | 46.7 C |
| 1.0 | 30% | No trip | 66.44 A | **2.336 V** | 46.9 C |
| 1.0 | 20% | CELL_UNDERVOLTAGE at 29.2 s | 66.88 A | **1.918 V** | 36.1 C |
| 0.4 | 90% | No trip | 59.91 A | 2.909 V | 45.1 C |
| 0.4 | 50% | No trip | 60.25 A | 2.612 V | 45.2 C |
| 0.4 | 30% | No trip | 60.44 A | **2.435 V** | 45.2 C |
| 0.4 | 20% | CELL_UNDERVOLTAGE at 46.8 s | 60.62 A | **2.046 V** | 42.2 C |

Observations:

1. At 30% SOC and below, cells are driven under the 2.5 V manufacturer cutoff with no protective action. At 20% SOC the eventual UVP trip occurs only after cells have reached 1.9 to 2.0 V.
2. Reducing assist from 1.0 to 0.4 lowers the surge peak by about 5 A only. The surge, not the gait load, dominates.
3. The DERATE_WARN ladder (torque scale 0.6) scales gait torque only; it does not reduce the surge.
4. Pack temperature rises about 21 C in 60 s from 25 C. With the 50 C warn and 55 C trip, an over-temperature trip is likely within the next 1 to 2 minutes. Thermal parameters are ASSUMED, so this rate is indicative only.

Assessment: the protection settings do not cover a repetitive sub-second overload. This scenario is a stress case (56 A dual-actuator peak each stride is not a measured load), but nothing in the current design prevents it.

## 4. Finding 2: low-SOC undervoltage margin

S13 at 12% SOC holds 20 mV above the 3.00 V UVP trip with the derate loop active. With the derate loop disabled (open loop), cells fall below the trip but are not tripped because each dip is shorter than the 0.5 s UVP delay:

| Assist | Start SOC | Derate loop | Peak current | Min cell V |
| --- | --- | --- | --- | --- |
| 1.0 | 12% | On | 10.27 A | 3.020 V |
| 1.0 | 12% | Off | 15.65 A | 2.882 V |
| 1.0 | 10% | On | 10.50 A | 2.947 V |
| 1.0 | 10% | Off | 16.10 A | 2.802 V |
| 0.4 | 12% | On | 3.43 A | 3.180 V |
| 0.4 | 10% | Off | 5.90 A | 3.049 V |

Assessment: below about 12% SOC at full assist, cell voltage under gait load sits at or below the UVP trip level. The UVP delay masks it. The derate loop, which is PROPOSED and not agreed with Controls (I-08), is what keeps S13 above the threshold. A low-SOC cut-off in the controller (for example, end assist at 15% SOC) is required regardless of the final ladder values.

## 5. Finding 3: the knee actuator, not the pack, sets the assist ceiling

The assist sweep at 90% SOC produced no BMS trip at any level from 0 to 100%. The binding constraint is the knee actuator's 12 A rated RMS phase current:

| Assist | Coupled peak pack current | Coupled mean pack current | Knee RMS phase current | Torque gap closed (L / R) | Time at 20 Nm limit (L / R) |
| --- | --- | --- | --- | --- | --- |
| 30% | 3.28 A | 1.64 A | 8.67 A | 30.0% / 30.0% | 0% / 0% |
| 40% | 4.53 A | 2.10 A | 11.56 A | 40.0% / 40.0% | 0% / 0% |
| 45% | 5.33 A | 2.35 A | **12.86 A** | 45.0% / 44.5% | 0% / 6.5% |
| 50% | 5.90 A | 2.56 A | 13.83 A | 48.9% / 47.7% | 4.5% / 12.5% |
| 75% | 10.51 A | 3.34 A | 17.37 A | 57.6% / 56.7% | 13.5% / 30.5% |
| 100% | 11.71 A | 3.86 A | 19.14 A | 59.3% / 58.2% | 18.5% / 48.0% |

Assessment:

1. The knee crosses 12 A RMS between 40% and 45% assist (linear interpolation: about 42%). Assist above that level is not thermally available for continuous walking.
2. Above 45% assist the 20 Nm torque limit clips, and the torque gap closed saturates near 59%. Raising assist from 75% to 100% adds 1.7 points of gap closure for 1.8 A more knee RMS current.
3. The default `ctl_assist = 1.0` used by S1, S7, S10 and S13 is a worst-case setting that the actuator cannot sustain. Scenario results at 1.0 are conservative for the pack.

## 6. Finding 4: fixed 48 V bus and runtime estimate

At assist 1.0 the MATLAB model's fixed 48 V bus and missing 45 W auxiliary load understate battery current:

| SOC | Open-circuit pack V | Peak, MATLAB 48 V | Peak, coupled | Peak error | Mean, coupled |
| --- | --- | --- | --- | --- | --- |
| 100% | 50.40 V | 10.33 A | 11.23 A | +8.8% | 3.71 A |
| 80% | 47.34 V | 10.33 A | 12.04 A | +16.6% | 3.96 A |
| 50% | 44.82 V | 10.33 A | 12.80 A | +23.9% | 4.20 A |
| 20% | 41.42 V | 10.33 A | 14.00 A | +35.6% | 4.56 A |
| 10% | 38.57 V | 10.33 A | 15.56 A | +50.7% | 4.97 A |

`derived.runtime_h_at_mean_current` reports 1.56 h. It is computed in `run_sim.py:56` as 4.5 Ah divided by the MATLAB mean of 2.88 A, which excludes the auxiliary load and the voltage effect. Using the coupled means of 3.71 to 4.97 A gives **0.9 to 1.2 h at assist 1.0**. At the thermally available 40% assist (coupled mean 2.10 A at 90% SOC) runtime is about 2 h. The 1.56 h figure should not be quoted until the formula is corrected.

## 7. Finding 5: regeneration and PD-14

- Peak braking power at the drivetrain is 8.3 W and braking energy is 0.0001 Wh per cycle at assist 1.0. The 45 W auxiliary load absorbs all of it, so S11, S12 and S14 deliver zero charge to the pack.
- Consequence: under this gait model the regeneration clamp (PD-14 option A) carries no energy, and S12 does not exercise the clamp at all. The scenarios as configured cannot size the clamp.
- Pack acceptance, from the regen envelope: 13.5 A (charge OCP binds) from 10 C to 45 C at 50 to 80% SOC; 4.3 A at 95% SOC and 1.1 A at 98% SOC at 25 C (overvoltage headroom binds); 0 A at or below 0 C.
- PD-14 can be deferred for walking on level ground. It cannot be closed: stair descent, sit-to-stand lowering and a controller fault that back-drives the motor are not modelled and are the cases that would generate significant braking power.

## 8. Items to confirm with Luis on the controls model

1. **Assist setting.** The gait data file metadata records `AssistanceFraction 0.15`, while the port runs at `ctl_assist = 1.0` (`sim/params.py:108`). Confirm which value the Electrical model's quoted 3 to 4 A mean refers to, and the intended operating assist.
2. **Motor loss model.** The metadata lists `MotorEfficiency 0.9`; the port uses a Km-based copper-loss model (Km 0.2387 Nm/sqrt(W), hot factor 1.3). Confirm the MATLAB script uses Km and not the fixed efficiency.
3. **MATLAB cross-check.** Run `one_sided_battery_current.m` in MATLAB at assist 1.0 and compare peak 10.33 A, mean 2.88 A, RMS 3.68 A. This remains the only check that catches a shared misreading of the MATLAB semantics.
4. **Derate ladder (I-08).** The 1.00 / 0.60 / 0.40 / 0.00 torque scales, 150 ms ramp and 1 s recovery hold are PROPOSED. Finding 2 shows the 0.60 step is load-bearing at low SOC, so this needs an agreed value.

## 9. Recommendations and open items

| # | Action | Driver | Owner |
| --- | --- | --- | --- |
| R1 | Add a pulse-overload protection in the motor controller (I^2t or a short-window current limit, for example 45 A averaged over 0.2 s) and make the controller scale actuator surge as well as gait torque under DERATE_WARN | Finding 1, RK-01 | Electrical / Controls |
| R2 | Evaluate a shorter UVP delay (for example 0.2 s) or a second, lower fast-acting UVP threshold, then re-run S2, S10 and S13 to check for nuisance trips | Findings 1, 2 | Electrical |
| R3 | Add a controller low-SOC cut-off (assist ends at about 15% SOC) independent of the BMS | Finding 2 | Controls |
| R4 | Set the operating assist ceiling at or below 40% for continuous walking, pending knee thermal test | Finding 3 | Controls |
| R5 | Correct `runtime_h_at_mean_current` to use the coupled mean current with auxiliary load, and stop quoting 1.56 h | Finding 4 | Electrical |
| R6 | Add regeneration scenarios for stair descent and sit-to-stand lowering before closing PD-14 | Finding 5 | Electrical |
| R7 | Close the four controls-model questions in Section 8 with Luis | Section 8 | Electrical / Luis |
| R8 | Add S10 at 30% SOC and 60 s to the standard scenario set so the gap stays visible | Finding 1 | Electrical |

## 10. Limitations

- No parameter is measured on EXO hardware and no BMS unit has been received (OI-09, PD-13). All BMS trip settings, derate values and the clamp threshold are PROPOSED; thermal capacitance and resistance, polarisation, DCIR temperature coefficient, bus capacitance and clamp resistance are ASSUMED.
- The 56 A dual-actuator surge profile is a stress case, not a measured load.
- Thermal results in Finding 1 depend on ASSUMED thermal parameters.
- Nothing in this report may justify a purchase, a part selection or a safety argument.

## Sources

- `ELEC-SIM-001_v1.5/CONTEXT.md`, `README.md`, `results/RESULTS_SUMMARY_v1.5.md` (2026-10-22 baseline)
- `results_2026-10-29/ELEC-SIM-001_Results_v1.5.json` (this run)
- Sensitivity runs: scratch script `sens.py`, 16 cases, using `sim.runner.Scenario` unchanged
