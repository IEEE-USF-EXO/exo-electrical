# results/

The JSON and the two figures in this folder were produced on the **synthetic
gait stand-in**, because the two Comparison_Data XML files live in
EXO > Electrical > Test Data and are not copied into the package. They set
`gait_data_is_authoritative: false`. **No number in them may be reported.**
They are a pipeline test. Nothing from this run was published to Drive.

## To produce the reportable results

1. Copy `PostStroke_Moco_Comparison_Data_Hemi.xml` and
   `Healthy_Gait_Comparison_Data.xml` from Electrical > Test Data into
   `../data/`.
2. Run `python run_sim.py`.
3. Check that the JSON reports `gait_data_is_authoritative: true`.
4. Before quoting any figure, compare the three `matlab_*_battery_A_at_48V`
   values against a MATLAB run of `one_sided_battery_current.m` at the same
   `assist`, `tauMax`, `hotFactor` and `velocityFrom`. They should agree to
   rounding. If they do not, the Python port is wrong (INTEGRATION.md
   Section 6).

The run writes:

| File | Contents |
| --- | --- |
| `ELEC-SIM-001_Results_v1.5.json` | Parameter table with a source per row, the fourteen scenario results, the assist ceiling study, the bus voltage study, the regen acceptance envelope and the braking budget |
| `ELEC-SIM-001_Overview_v1.5.png` | Protection overview: nominal gait, the 56 A surge trip, the regen acceptance envelope, cell overvoltage during balancing |
| `ELEC-SIM-001_Integration_v1.5.png` | Assist sweep through the protection layer, the fixed-voltage comparison, the regeneration budget, and the closed-loop derate during a telemetry dropout |

The v0.1 results remain in the parent Drive folder for comparison. Note that
v1.5 changed the OCV curve and added the busbar and FET resistance, so cell
voltages and pack voltage under load are not directly comparable between the
two issues (CHANGELOG.md).
