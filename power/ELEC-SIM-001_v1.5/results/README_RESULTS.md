# results/

Output of the run of 2026-10-22 on the authoritative gait data. Start with
**`RESULTS_SUMMARY_v1.5.md`**: it carries the headline numbers and what they
mean for ELEC-013 to ELEC-015, PD-14, RK-01 and RK-03.

| File | Contents |
| --- | --- |
| `RESULTS_SUMMARY_v1.5.md` | Authored summary. Every number read from the JSON. |
| `ELEC-SIM-001_Results_v1.5.json` | Machine output: parameter table with a source per row, fourteen scenario results, the assist ceiling study, the bus voltage study, the regen acceptance envelope and the braking budget. |
| `ELEC-SIM-001_Overview_v1.5.png` | Nominal gait, the 56 A surge trip, the regen acceptance envelope, cell overvoltage during balancing. |
| `ELEC-SIM-001_Integration_v1.5.png` | Assist sweep through the protection layer, the fixed-voltage comparison, the regeneration budget, the closed-loop derate during a telemetry dropout. |

## Run of record

| Field | Value |
| --- | --- |
| Date | 2026-10-22 |
| Gait input | `PostStroke_Moco_Comparison_Data_Hemi.xml`, 201 samples, from Drive Electrical > Test Data |
| `gait_data_is_authoritative` | true |
| Assist | 1.0, `tauMax` 20 Nm, `hotFactor` 1.3, velocity from the weak leg |
| Auxiliary load | 45 W |
| Sweep SOC | 90% |

## To regenerate

```
python run_sim.py
```

with the two Comparison_Data XML files in `../data/`. They are not committed
here: raw test data stays in Drive (Electrical > Test Data), and the
simulation should read the Electrical team's own file rather than a stale
duplicate in this repo. `../data/README_DATA.md` gives the two file names and
their Drive IDs.

A run takes a few minutes. Confirm `gait_data_is_authoritative: true` in the
JSON before quoting anything from it; without the XML files the run falls
back to a synthetic stand-in and flags itself as not reportable.

## Comparing against v0.1

The v0.1 results are in the Drive folder Electrical > Kiboard warriors. They
are not directly comparable: v1.5 changed the OCV curve to the
`battery_ocv.m` pchip shape and added 0.020 ohm of busbar and FET resistance,
so cell voltages and pack voltage under load differ for the same current.
v0.1 was also driven by a synthetic current profile rather than by the
Electrical gait control model. See `../CHANGELOG.md`.
