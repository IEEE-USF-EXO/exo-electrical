# INTEGRATION: how the models couple

Companion to CONTEXT.md. This file is the interface specification between the
Electrical gait control model, the pack and BMS model, and the surge and
regeneration modules. Anyone changing one of the three should read it first.

---

## 1. Conventions

Both models already agree on these. Do not change them on one side only.

| Quantity | Convention |
| --- | --- |
| Pack current `I` | Positive discharges the pack, negative charges it |
| Bus power `P` | Positive discharges the pack, negative is net regeneration |
| Joint torque | Model-internal, from the OpenSim data; not reinterpreted here |
| Cell voltage | Per cell. Pack voltage is the sum plus the busbar and FET drop |
| Time | Seconds from the start of the exported window |
| Gait phase | Percent of one gait cycle, 0 to 100 |

---

## 2. Coupling point: power, not current

The two models could be joined at three places. v1.5 joins them at bus power.

| Join at | Consequence |
| --- | --- |
| Joint torque | Would require the pack model to carry the whole drivetrain. Duplicates the control model. Rejected. |
| **Bus power** | The control model's natural output. The pack solves its own current against its own terminal voltage. **Used.** |
| Battery current | Freezes the bus voltage assumption into the interface, which is exactly the error v1.5 exists to remove. Supported for playback only. |

At every step the pack solves

    P = (V_src - I * R_pack) * I

for the lower-current root, which is the same algebra as
`pack_current_from_power.m` in the AK80 model:

    I = ( V_src - sqrt( V_src^2 - 4 * R_pack * P ) ) / ( 2 * R_pack )

`V_src` is the sum of cell open-circuit voltages less the polarisation
voltage. `R_pack` is the sum of cell DC resistances at the present SOC and
temperature, plus `pack_extra_r_ohm` for busbar, FET and harness.

A negative discriminant means the pack cannot deliver that power at any
current. The runner counts those steps in `power_solve_infeasible_steps`. A
nonzero count is a voltage-collapse condition and invalidates the run.

---

## 3. Signal flow, one time step (1 ms)

```
  controller torque scale k (from the previous step)
            |
            v
  gait control model: ta = clip(assist * k * (tau_strong_shifted - tau_weak), +/- tauMax)
            |  drivetrain: gear, inverter, hot copper loss
            v
  P_bus [W]  =  sum over hip and knee  +  auxiliary load (45 W)
            |
            v
  pack solve:  I_cmd = f(P_bus, V_src, R_pack)
            |
            + surge module: I_cmd += surge(t)
            v
  regen module (only when I_cmd < 0): split into accepted and rejected
            |
            v
  BMS gate: discharge path and charge path, each latched independently
            |
            v
  pack step: SOC, polarisation, temperature
            |
            v
  telemetry: 10 Hz sample, staleness test, derate decision
            |
            +--> torque scale k for the next step
```

The derate feedback is the only path from the controller back into the load.
There is no path from the controller into the BMS: protection is independent
of firmware (ELEC-DOC-007 M-08) and must stay that way.

---

## 4. Data contract: the MATLAB export

`matlab/export_bms_profile.m` runs next to `one_sided_battery_current.m` and
writes a CSV with these columns:

| Column | Unit | Required | Meaning |
| --- | --- | --- | --- |
| `t_s` | s | yes | Time from the start of the window |
| `P_W` | W | preferred | DC-bus power, positive discharges the pack |
| `I_A` | A | optional | Battery current at the fixed 48 V, as the MATLAB model reports it |
| `phase_pct` | % | optional | Gait cycle percentage, for plotting |

Rules:

- A profile with `P_W` is solved against the live pack voltage and can run the
  closed-loop scenarios.
- A profile with only `I_A` is played back as given. It cannot respond to pack
  voltage sag or to a derate, so it may not be used for S1, S7, S10 or S13.
- The export repeats the cycle `cycles` times. The Python side also wraps a
  single cycle, so either is acceptable.
- `export_bms_profile.m` defaults to the same options as the source model,
  plus a 45 W auxiliary load and no regeneration credit. Changing those
  defaults changes the meaning of the profile: say so when you hand one over.

---

## 5. Where the two models differ, deliberately

| Item | MATLAB control model | ELEC-SIM-001 v1.5 | Why |
| --- | --- | --- | --- |
| Bus voltage | Fixed 48 V | Live pack terminal voltage | A 12S1P pack runs 50.4 V to 36 V and sags about 0.20 ohm times current |
| Braking samples | `Pb = 0` when `Pe <= 0` | Regeneration module decides acceptance, rejection and clamp duty | PD-14 needs the energy figure |
| Auxiliary load | Not present | 45 W nominal, 65 W conservative available | The Jetson and Teensy are on the pack |
| Protection | None | Full BMS state machine | ELEC-015 |
| Controller | Open loop | Derate ladder feeds back into commanded torque | ELEC-014, M-06 |
| Temperature | Not modelled | Lumped thermal state, ASSUMED parameters | Charge acceptance depends on it |

Everything else is ported unchanged, including the weak-side selection, the
correlation-based stride alignment, the 20 Nm torque clip, the hot-winding
factor of 1.3 and all four drivetrain efficiencies.

---

## 6. Verifying the port

Before a result is reported, check the port against the source model at the
same settings. `summary()` reports three figures in exactly the form
`one_sided_battery_current.m` prints them:

    matlab_peak_battery_A_at_48V
    matlab_mean_battery_A_at_48V
    matlab_rms_battery_A_at_48V

Run the MATLAB model with the same `assist`, `tauMax`, `hotFactor` and
`velocityFrom`, and compare. These should agree to rounding, because the
Python path reproduces the same arithmetic with no pack coupling, no
auxiliary load and no regeneration credit. A disagreement means the port is
wrong; fix the port, not the MATLAB.

The peak exo torque, the percentage of the cycle at the torque limit, the gap
closed per joint and the per-actuator phase currents are reported for the
same reason.

**Status, 2026-10-22.** The port was checked against an independent
re-implementation written from the MATLAB source and sharing no code with it
(peak 10.33 A, mean 2.88 A, RMS 3.68 A on both, maximum difference 0.0041 A).
That rules out a transcription error. It does not rule out a misreading of
the MATLAB semantics that both implementations share, so **the comparison
against a MATLAB run itself is still open** and is the first task on this
package.

---

## 7. Known coupling weaknesses

1. The regeneration module evaluates pack voltage from the source voltage
   rather than from the solved terminal voltage within the same step. The
   error is the resistive drop at the accepted current, under 1 V at the
   13.5 A charge limit. It is not corrected because the acceptance limit is
   itself bounded by a cell-voltage headroom of 20 mV that is PROPOSED.
2. The surge module adds current, not power. A surge is therefore not reduced
   by pack voltage sag within the step it is applied. This is conservative.
3. The derate ladder applies a torque scale uniformly to hip and knee. A real
   controller would be free to derate one joint. Nothing here requires that
   choice; it is the simplest assumption and it is PROPOSED.
4. Balancing moves charge between cells at 1 A with no loss term.
5. The gait data is a single predicted cycle repeated. Stride-to-stride
   variation, stumbles, stairs and sit-to-stand are not represented. S10 adds
   a repeated peak demand as a stand-in for an event load, not as a model of
   one.
