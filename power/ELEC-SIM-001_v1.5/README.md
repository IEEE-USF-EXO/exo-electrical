# ELEC-SIM-001 v1.5

Integrated battery-management simulation for the EXO Phase 1 12S1P pack.
Kiboard Warriors workstream, packages ELEC-013 to ELEC-015.

v1.5 couples three pieces of work that were separate until now:

- the BMS protection and telemetry logic from ELEC-SIM-001 v0.1,
- the Electrical team's gait control model, `one_sided_battery_current.m`
  (Drive: EXO > Electrical > Test Data), with its OpenSim Moco gait data,
- new surge and regeneration modules that cover the two load paths neither of
  the above carries.

Read **CONTEXT.md** before using any output. It states what is measured, what
is proposed, what is assumed, and what this model may not be used for. Short
version: nothing here has been measured on EXO hardware, no BMS unit has been
received, and no value in this package may justify a purchase, a selection or
a safety argument.

**No results are published with this issue.** The gait data lives in
Electrical > Test Data and is not duplicated here, so the results have to be
generated locally. See "Before the first real run" below.

## Layout

```
ELEC-SIM-001_v1.5/
  CONTEXT.md          read first: sources, assumptions, traceability, limits
  INTEGRATION.md      how the three models couple, and the data contract
  CHANGELOG.md        what changed from v0.1, and why
  run_sim.py          entry point
  sim/
    params.py         every parameter with its source tag
    gaitctl.py        port of the Electrical gait control model (primary load)
    gait.py           AK80 sizing model (secondary, cross-check only)
    pack.py           12S1P cell, DCIR, polarisation, thermal
    bms.py            protection state machine, separate charge/discharge paths
    regen.py          charge acceptance, rejected energy, clamp (PD-14)
    surge.py          inrush, dual-actuator peak, bolted fault
    telemetry.py      10 Hz consumer, staleness, derate ladder
    scenarios.py      S1 to S14 and the two parameter studies
    runner.py         the 1 ms coupled loop
  matlab/
    export_bms_profile.m   writes a load profile from the MATLAB model
  data/
    (copy the two Comparison_Data XML files here before any real run)
    fukuchi_young_overground_engineering_template.csv   secondary source data
  results/
    ELEC-SIM-001_Results_v1.5.json
    ELEC-SIM-001_Overview_v1.5.png
    ELEC-SIM-001_Integration_v1.5.png
```

## Before the first real run

The gait data files are not redistributed in this folder. Copy both from
Drive, EXO > Electrical > Test Data, into `data/`:

- `PostStroke_Moco_Comparison_Data_Hemi.xml` (primary)
- `Healthy_Gait_Comparison_Data.xml` (comparison)

Without them the run falls back to a synthetic stand-in, prints a warning and
sets `gait_data_is_authoritative: false` in the results JSON. A run with that
flag false is a pipeline test, not a result.

## Run

```
python run_sim.py                       # all scenarios and both studies
python run_sim.py --assist 0.5 --soc 0.5
python run_sim.py --data data/Healthy_Gait_Comparison_Data.xml
python run_sim.py --no-figures
```

Python 3.9 or newer with numpy and matplotlib. scipy is optional and makes
the OCV interpolation match the MATLAB `pchip` call exactly.

A full run takes a few minutes: the loop steps at 1 ms so the 10 ms
short-circuit delay is resolved, and the assist sweep repeats that loop at
every sweep point.

## What it produces

`results/ELEC-SIM-001_Results_v1.5.json` holds the parameter table with a
source per row, the fourteen scenario results, and three studies:

| Key | Question it answers |
| --- | --- |
| `assist_ceiling_study` | How high can the assist level go before the pack or the BMS, rather than the actuator, becomes the limit |
| `bus_voltage_study` | How much the fixed 48 V in the MATLAB model understates battery current, per state of charge |
| `regen_acceptance_envelope` | How much charge current the pack accepts across state of charge and temperature, and which limit binds |
| `gait_control_model.braking_budget_at_configured_assist` | How much braking energy exists per gait cycle, how much the auxiliary load absorbs, and how much reaches the pack (PD-14 input) |

Two figures are written alongside it: a protection overview and an
integration figure.

## Open items this package feeds

- **PD-14**, regeneration clamp: `regen.py`, scenarios S11 and S12, and the
  braking budget give the energy, the peak power and the duty.
- **RK-03**, precharge not chosen: `derived.inrush_without_precharge` shows
  that the inrush transient is far shorter than the 10 ms short-circuit delay,
  so the BMS does not protect against it.
- **RK-01**, 56 A against the 45 A cell rating: `derived.stacked_worst_case`
  and scenario S10.
- **I-08**, battery data interface: the derate ladder in `telemetry.py` is the
  proposal to review with Controls. It is not agreed.
