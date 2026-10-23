# CONTEXT: ELEC-SIM-001 v1.5

Read this before changing anything in this folder, or before quoting any
number it produces. It states what the simulation is, what it is built from,
what is assumed, and what it may not be used for.

| Field | Value |
| --- | --- |
| Package | ELEC-SIM-001, v1.5 |
| Supersedes | ELEC-SIM-001 v0.1 (2026-10-20) |
| Date | 2026-10-22 |
| Team | Kiboard Warriors (Electrical sub-team: James, Mohid, Liam) |
| Work packages | ELEC-013 (BMS integration concept), ELEC-014 (monitoring and communication requirements), ELEC-015 (initial simulation of monitoring behaviour) |
| Companion document | ELEC-DOC-007 BMS Integration Concept and Monitoring Requirements, v0.1 |
| Gate target | PDR, Thu Oct 29 |
| Status | Preliminary. No parameter in this model has been measured on EXO hardware. |

---

## 1. What v1.5 is

v0.1 was a BMS protection state machine exercised by synthetic current
profiles. It answered one question: given a current waveform, does the
protection act as intended.

v1.5 replaces the synthetic profiles with the Electrical team's own gait
control model and adds the two load paths that model does not carry. The
simulation now contains five coupled layers:

| Layer | Module | Origin |
| --- | --- | --- |
| Gait control | `sim/gaitctl.py` | Port of `one_sided_battery_current.m` (Electrical > Test Data) |
| Pack | `sim/pack.py` | Molicel P45B 12S1P, OCV shared with `battery_ocv.m` |
| Protection | `sim/bms.py` | JK-B1A24S15P candidate, separate charge and discharge paths |
| Regeneration | `sim/regen.py` | New in v1.5, answers PD-14 |
| Surge | `sim/surge.py` | New in v1.5, inrush, dual-actuator peak, bolted fault |
| Telemetry and derate | `sim/telemetry.py` | ELEC-DOC-007 M-05 to M-08, now closed loop |

The loop runs at 1 ms so the 10 ms short-circuit delay is resolved.

---

## 2. Source models, and which one wins

### 2.1 Primary: the Electrical control model

Drive: **EXO > Electrical > Test Data**

| File | Drive ID | Role |
| --- | --- | --- |
| `one_sided_battery_current.m` | `1GuL6SPkEZCvy-13y5pJZoSzvVO283Mw2` | One-sided assist controller and battery current. Ported in full. |
| `battery_current.m` | `1Foydp_YpgJVWap7lfO5_DZ4MplQVWzvi` | Simpler per-joint percentage variant of the same drivetrain. |
| `PostStroke_Moco_Comparison_Data_Hemi.xml` | `1EcJNvP4BA77Z-tn3DempkNaTSOaP6c3M` | 201 samples, hemiparetic, OpenSim Moco prediction. Primary input. |
| `Healthy_Gait_Comparison_Data.xml` | `1M5DLi3_UcRqry4SMEb-XPTmnNWcjH1A1` | 135 samples, healthy, OpenSim inverse dynamics, 6 Hz low pass. |
| `MATLAB_battery_current_modeling.jpg` | `1jrqOVuA5tDVquUBV6yeTA7zMDiuG_L_S` | Result figure. |

The control law, verbatim from the source model: the exoskeleton sits on the
weaker leg, the stronger leg's torque is re-timed by a circular shift that
maximises angular-velocity correlation, and the commanded assist torque is

    ta = clip( assist * (tau_strong_shifted - tau_weak),  +/- tauMax )

with `tauMax` 20 Nm, gear ratio 9, gearbox efficiency 0.90, controller
efficiency 0.95, Kt 0.095 Nm/A, Km 0.2387 Nm/sqrt(W) and a hot-winding copper
factor of 1.3. Braking samples take no regeneration credit: `Pb = 0` wherever
`Pe <= 0`. This model is the basis of the 3 to 4 A mean battery current quoted
on the Electrical biweekly sheet of 2026-10-12 and in ELEC-DOC-007 Section 4.

**If the Python port and the MATLAB source disagree, the MATLAB source is
correct and the port is wrong.** Do not reconcile a difference by editing the
MATLAB file. Report it.

### 2.2 Secondary: the AK80 sizing model

`EXO_AK80_Battery_Gait_Model_v2_2` (author Gustavorodriguezpc) is ported in
`sim/gait.py` as a cross-check only. It uses different gait data (Fukuchi
healthy overground template), a different assist law (a fixed percentage of
the healthy biological moment) and a different loss model. It is useful for
bounding a result, not for producing one. The two models are not averaged.

### 2.3 Data files are not in this folder

The two XML files are not redistributed here. Copy them from Drive into
`data/` before producing any reportable result. Without them `run_sim.py`
falls back to a synthetic stand-in, prints a warning, and marks
`gait_data_is_authoritative: false` in the results JSON. **A run with that
flag false is a pipeline test and nothing else.**

---

## 3. What the coupling changes, and why it matters

Four differences between the control model run on its own and the same model
run against the pack. Each one is a reason this integration exists.

1. **Fixed bus voltage.** The MATLAB model divides bus power by a constant
   48 V. A 12S1P pack is 50.4 V full and 43.2 V nominal, with roughly 0.20 ohm
   of series resistance including busbar and FET. Battery current at a given
   power is therefore higher than the MATLAB figure, and the error grows as
   SOC falls. `bus_voltage_study` in the results JSON quantifies it per SOC,
   and separates the voltage effect from the auxiliary-load effect.

2. **Discarded braking energy.** `Pb(Pe <= 0) = 0` is conservative for sizing
   and silent about disposal. The regeneration module computes what the pack
   will accept against four limits (cell overvoltage headroom, the 13.5 A
   charge overcurrent setting, the 0 C to 60 C charge temperature window, and
   state of charge) and reports the remainder as energy that the drive must
   refuse or a clamp must dissipate. This is the input PD-14 was deferred
   pending.

3. **No auxiliary load.** The Jetson Orin Nano, the Teensy and the sensors
   (45 W nominal, 65 W conservative) are not in the MATLAB model and are on
   the pack. v1.5 adds 45 W by default (`ctl_include_aux_load`). Note the
   consequence for regeneration: the pack only sees charge when braking power
   exceeds the auxiliary load.

4. **No protection layer.** The assist sweep in the source model reports peak
   and mean current against assist level with nothing to stop it.
   `assist_ceiling_study` runs each sweep point through the pack and the BMS
   and reports the highest assist level that does not trip, with the binding
   protection named. A level that does not trip may still be unavailable for
   thermal reasons: compare `knee_rms_phase_A` against the 12 A rated phase
   current before reading a level as available.

---

## 4. Closed-loop behaviour (new, and the main modelling risk)

In v0.1 the telemetry consumer logged a derate decision. In v1.5 it returns a
torque scale factor that multiplies the commanded assist torque on the next
step, so a BMS warning reduces pack current inside the same run. The ladder
is:

| Controller mode | Commanded torque | Trigger |
| --- | --- | --- |
| NORMAL | 1.00 | fresh telemetry, no warning |
| DERATE_WARN | 0.60 | any BMS warning flag |
| DERATE_STALE | 0.40 | telemetry older than 500 ms |
| STOP_TORQUE | 0.00 | discharge path open |

**Every value in that table is PROPOSED and has no Controls agreement on
record.** Interface I-08 is a draft. The ladder, the 150 ms first-order ramp
and the 1 s recovery hold were chosen here so the loop could be exercised at
all, not because anyone has agreed to them. They are the first thing to
settle with Oscar and Tom, and the first thing to change if the loop is seen
to oscillate.

The feedback does not weaken the protection layer. `sim/bms.py` takes no
input from `sim/telemetry.py`, which satisfies ELEC-DOC-007 M-08. Nothing in
the BMS module may be made dependent on telemetry.

---

## 5. Scenarios

S1 to S9 carry over from v0.1 so the earlier results stay comparable; S1, S7
and S9 are now driven by the gait control model. S10 to S14 are new.

| ID | Scenario | What it tests |
| --- | --- | --- |
| S1 | Nominal gait, closed loop | Ordinary walking does not approach any trip |
| S2 | 56 A dual-actuator demand on top of gait | Discharge overcurrent, 45 A at 1.0 s |
| S3 | Bolted fault, 150 A | Short circuit, 100 A at 10 ms |
| S4 | 10 A charge step at 95% SOC | Charge overcurrent and cell overvoltage |
| S5 | 4.5 A charge, one cell 12% high | Balancing and cell overvoltage |
| S6 | Thermal ramp at 3.5 A | Over-temperature warn and trip |
| S7 | 2 s telemetry dropout during gait | M-06 staleness, and the derate loop |
| S9 | Charge at minus 5 C | Charge temperature inhibit |
| S10 | Dual-actuator peak once per stride | Repeated surge on a live gait load |
| S11 | Gait with regeneration at 98% SOC, no clamp | Regen the pack cannot accept |
| S12 | Same, clamp fitted | PD-14 option A, clamp energy and duty |
| S13 | Gait at 12% SOC | Sag, undervoltage margin, derate under load |
| S14 | Gait with regeneration at 40% SOC | Regen the pack can accept |

---

## 6. Parameter status

`sim/params.py` carries every number with a source tag. Three classes:

- A manufacturer document or a named project file. Usable.
- `PROPOSED`. A setting this workstream suggests for team review. Not agreed.
  All BMS trip settings, all derate values and the clamp threshold are here.
- `ASSUMED`. A placeholder with no source at all. The thermal capacitance and
  resistance, the polarisation branch, the DCIR temperature coefficient, the
  bus capacitance and the clamp resistor are here.

`results/ELEC-SIM-001_Results_v1.5.json` lists the full set under
`parameters_not_cleared_for_design_use`. **No value from that list may be used
to justify a purchase, a selection or a safety argument.**

Known gaps, in priority order:

1. No measured OCV curve. The pchip shape from `battery_ocv.m` is a sizing
   curve. Cell voltage near the trip thresholds is therefore approximate, and
   the regen acceptance figures depend directly on it.
2. No thermal data. `pack_cth_J_per_K` and `pack_rth_K_per_W` are estimates.
   S6 timing and the high-temperature regen taper follow from them.
3. No BMS unit on hand. Every JK-B1A24S15P behaviour is from datasheets and
   community documentation (OI-09, PD-13). Trip delays and the port type are
   unconfirmed on the delivered unit.
4. No bench current log. Technical Baseline 6.3 requires battery selection to
   follow logged current. This model is not a substitute for that log.
5. The healthy XML shows knee angular velocities above 20 rad/s, which is
   high for a filtered IK derivative. Confirm the derivative and filter
   settings before using the healthy file for anything but comparison.

---

## 7. Traceability

| Item | Where v1.5 addresses it |
| --- | --- |
| ELEC-013 | Protection layering and parameter table, Sections 2 and 6 |
| ELEC-014 | Telemetry rate, staleness and derate behaviour, S7 and Section 4 |
| ELEC-015 | The whole scenario set, S1 to S14 |
| M-04, M-05, M-06 | `sim/telemetry.py`, S7 |
| M-08 | `sim/bms.py` takes no firmware input |
| PD-06 | Pack configuration against logged current: `assist_ceiling_study` gives the current the control model demands, not a substitute for the log |
| PD-13 | Boundary respected: this is BMS and telemetry investigation, not battery selection |
| PD-14 | `sim/regen.py`, S11 and S12: rejected energy, clamp energy, peak clamp power and duty |
| RK-01 | 56 A against the 45 A cell rating: `derived.stacked_worst_case` |
| RK-03 | Precharge: `derived.inrush_with_precharge` and `inrush_without_precharge` |
| OI-09 | Unresolved. Actuator input voltage limits are not confirmed; the 52 V driver maximum appears only as the clamp threshold rationale |

---

## 8. Running it

```
python run_sim.py --outdir results
python run_sim.py --data data/Healthy_Gait_Comparison_Data.xml --assist 0.5 --soc 0.5
```

Requires Python 3.9 or newer, numpy and matplotlib. scipy is optional: with it
the OCV interpolation matches the MATLAB pchip call exactly, without it a
linear interpolation on the same knots is used and the difference is noted in
`derived.ocv_interpolation`.

To drive the Python simulation from MATLAB instead of from the port, run
`matlab/export_bms_profile.m` next to `one_sided_battery_current.m` and pass
the CSV it writes. Prefer the `P_W` column: a current-only profile cannot
respond to pack voltage sag or to a derate, so it cannot run the closed-loop
scenarios.

---

## 9. What this model may not be used for

- Selecting the BMS, the cells, the clamp or the precharge resistor.
- Justifying a purchase.
- Any safety argument. Gates S1 and S3 are hardware gates and no simulation
  closes them.
- Claiming the protection settings are correct. They are proposed values
  exercised against a model of the pack, not verified against a unit.

What it is for: showing that the protection logic behaves as intended against
the loads the Electrical control model actually predicts, finding the assist
level at which the pack rather than the actuator becomes the limit, and
putting numbers on PD-14 so the decision can close.

---

## 10. State of this issue

Run on the authoritative data on 2026-10-22, with both Comparison_Data XML
files copied into `data/` from Electrical > Test Data. The run reports
`gait_data_is_authoritative: true`. Results and what they mean are in
`results/RESULTS_SUMMARY_v1.5.md`.

The port was checked against an independent re-implementation written from
the MATLAB source and agrees to 0.0041 A on all three reported battery
currents. That catches a transcription error in the port; it does not catch a
misreading of the MATLAB semantics shared by both. **Running
`one_sided_battery_current.m` itself and comparing the three figures is still
open.**

The headline results:

- No assist level from 0 to 100% trips the pack. The limit is the knee
  actuator: RMS phase current crosses the 12 A rating between 40% and 45%
  assist and reaches 19.1 A at 100%.
- The fixed 48 V assumption understates battery current by 9% at full charge
  and 51% at 10% SOC, of which roughly half is the missing auxiliary load.
- Regeneration from gait is negligible, 0.007 Wh per minute at the
  drivetrain and nothing at the pack. PD-14 cannot be closed in favour of the
  clamp on the gait case.
- A 65 A demand of 0.4 s repeated once per stride trips nothing, because it
  is under the 100 A short-circuit threshold and shorter than the 1.0 s
  overcurrent delay (RK-01).
- Inrush without a precharge resistor is 250 A for 0.6 ms, far inside the
  10 ms short-circuit delay, so the BMS gives the contactor no cover (RK-03).

Still outstanding: the MATLAB comparison above, and review of the derate
ladder in Section 4 with Controls (Oscar, Tom) as the I-08 draft.
