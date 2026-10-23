# CHANGELOG

## v1.5, 2026-10-22

Integration release. v0.1 was a protection state machine driven by synthetic
current waveforms. v1.5 drives it with the Electrical team's own gait control
model and adds the surge and regeneration paths.

### Added

- **Gait control coupling** (`sim/gaitctl.py`). Full port of
  `one_sided_battery_current.m` from Drive, EXO > Electrical > Test Data:
  weak-side selection, correlation-based stride alignment, the
  weak-to-strong torque gap assist law, the 20 Nm clip, the hot-winding
  copper factor of 1.3 and all four drivetrain efficiencies. Reads the
  `Comparison_Data` XML files directly.
- **Regeneration module** (`sim/regen.py`). Charge acceptance against four
  limits (cell overvoltage headroom, the 13.5 A charge overcurrent setting,
  the charge temperature window, state of charge), an energy ledger
  separating accepted, rejected and clamp-dissipated energy, clamp duty, and
  a two-dimensional acceptance envelope over SOC and temperature. Feeds
  PD-14.
- **Surge module** (`sim/surge.py`). Closed-form inrush analysis with and
  without the precharge resistor, dual-actuator peak surges superimposed on a
  live gait load, repeating per-stride surges, bolted fault, stacked
  worst-case table and maximum pulse duration against the trip delays.
- **Closed-loop derate.** The telemetry consumer now returns a torque scale
  that multiplies the commanded assist torque on the next step, with a
  first-order ramp and a recovery hold. A BMS warning therefore reduces pack
  current inside the run.
- **Separate charge and discharge FET states** in the protection state
  machine, as on the JK-B1A24S15P candidate. Cell overvoltage, charge
  overcurrent and charge temperature violations now open the charge path only,
  so the exoskeleton keeps walking while the pack stops accepting charge.
- **Scenarios S10 to S14**: per-stride surge on gait, regeneration at 98% SOC
  with and without the clamp, gait at 12% SOC, regeneration at 40% SOC.
- **`assist_ceiling_study`**: the MATLAB assist sweep re-run through the pack
  and the BMS, reporting the highest assist level that does not trip and the
  protection that binds first.
- **`bus_voltage_study`**: fixed 48 V against the live pack voltage across
  state of charge.
- **`braking_budget`**: braking energy per gait cycle at the drivetrain, the
  part the auxiliary load absorbs, and the part that reaches the pack.
- **`matlab/export_bms_profile.m`**: writes a load profile from the MATLAB
  model so a result can be traced to it rather than to the Python port.
- **Thermal state**: lumped pack temperature with heating from resistive and
  polarisation losses. Parameters are ASSUMED.
- **First-order polarisation branch** per cell, matching the role of `Rp` and
  `Cp` in `battery_gait_ode_rhs.m`.
- **SOC- and temperature-dependent DC resistance**, with the low-SOC
  multiplier taken from `exo_model_config.m`.
- **CONTEXT.md and INTEGRATION.md.**

### Changed

- **OCV curve.** The v0.1 linear placeholder (3.0 V at 0%, 4.2 V at 100%) is
  replaced by the pchip shape in `battery_ocv.m`, so this model and the
  Electrical battery model now share one OCV. Still a sizing curve, not a
  measurement. Cell voltages near the trip thresholds differ from v0.1.
- **Pack resistance** now includes `pack_extra_r_ohm` (0.020 ohm) for
  busbar, FET and harness, from `exo_model_config.m`. Pack voltage under load
  is therefore lower than in v0.1.
- **S1, S7 and S9** are driven by the gait control model instead of the
  synthetic `profile_gait` pulse train, and S1 and S7 run closed loop.
- **S2 and S3** apply their surge on top of a running gait load rather than
  from a flat baseline.
- **Regen sweep** (v0.1, SOC only, at 25 C) is replaced by the two-dimensional
  acceptance envelope with the binding limit named per cell.
- **Results JSON** gains the gait control model block, the three studies, the
  derived inrush and stacked-surge tables, and an explicit
  `parameters_not_cleared_for_design_use` list.
- **Figures** are renamed `ELEC-SIM-001_Overview_v1.5.png` and
  `ELEC-SIM-001_Integration_v1.5.png`.

### Not changed

- All BMS trip settings keep their v0.1 values, and all remain PROPOSED.
- No parameter has been measured on EXO hardware. No BMS unit has been
  received (OI-09, PD-13).
- The model still may not be used to select a part, justify a purchase or
  support a safety argument.

### Known issues

- The two gait XML files are not redistributed with the package. Without them
  the run uses a synthetic stand-in and flags itself as not reportable. No
  results are published with this issue for that reason.
- The port has not yet been checked against a MATLAB run at matched settings.
  See INTEGRATION.md Section 6 for the three figures to compare.
- Full runtime is a few minutes because the loop steps at 1 ms.

## v0.1, 2026-10-20

First issue. BMS protection state machine and Teensy telemetry consumer for
the 12S1P pack, exercised by scenarios S1 to S9 with synthetic current
profiles, a linear OCV placeholder and a SOC-only regen sweep. Companion to
ELEC-DOC-007 v0.1.
