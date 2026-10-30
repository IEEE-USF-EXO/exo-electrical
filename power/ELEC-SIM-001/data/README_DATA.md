# data/

## Required before any reportable run

Copy these two files here from Drive, **EXO > Electrical > Test Data**:

| File | Drive ID | Samples | Used as |
| --- | --- | --- | --- |
| `PostStroke_Moco_Comparison_Data_Hemi.xml` | `1EcJNvP4BA77Z-tn3DempkNaTSOaP6c3M` | 201 | Primary gait input |
| `Healthy_Gait_Comparison_Data.xml` | `1M5DLi3_UcRqry4SMEb-XPTmnNWcjH1A1` | 135 | Comparison only |

They are not copied into this package, so the simulation always reads the
Electrical team's own file rather than a stale duplicate. `run_sim.py` looks
for the hemiparetic file first, then the healthy file.

If neither is present the run falls back to a synthetic stand-in, prints a
warning, and sets `gait_data_is_authoritative: false` in the results JSON.
**A run with that flag false is a pipeline test and no number from it may be
reported.**

## Already here

| File | Role |
| --- | --- |
| `fukuchi_young_overground_engineering_template.csv` | Gait template for the secondary AK80 sizing source (`sim/gait.py`), copied from `EXO_AK80_Battery_Gait_Model_v2_2/data/`. Cross-check only. |
| `FUKUCHI_TEMPLATE_NOTES.md` | Provenance of that template, as written by the AK80 model author. |

## Note on the healthy file

Its knee angular velocities reach above 20 rad/s, which is high for a
filtered inverse-kinematics derivative at a 6 Hz low pass. Confirm the
derivative and the filter settings before using the healthy file for anything
beyond comparison.
