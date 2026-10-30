"""Secondary gait load source: the AK80 battery sizing model.

The primary gait source for v1.5 is sim/gaitctl.py, the port of the Electrical
team's one-sided assist control model in Drive under EXO > Electrical > Test
Data. This module is the cross-check: a different model, different gait data
and a different assist law, used to bound the first one. Where the two
disagree, say so rather than averaging them.

Two sources of DC-bus load are provided here:

1. GaitChain, a step-for-step port of the biomechanics-to-DC-bus chain in
   simulate_gait_cycle.m and exo_model_config.m from the Electrical AK80
   battery/gait MATLAB model (EXO_AK80_Battery_Gait_Model_v2_2, author
   Gustavorodriguezpc, maintained in the Electrical workstream). It reads the
   same Fukuchi engineering template CSV. It is a port, not an export: if the
   two ever disagree, the MATLAB model is authoritative and the port is wrong.
   Chain:
       Fukuchi phase -> joint angle and moment per kg -> x wearer mass ->
       x assist fraction -> commanded torque -> clip to actuator peak torque ->
       q-axis current -> mechanical power -> gearbox, inverter, copper and idle
       losses -> hip + knee DC power -> plus the electronics load.

2. GaitCsvSource, playback of a CSV exported from the MATLAB model itself
   (matlab/export_bms_profile.m writes it). Use this for any result that
   must trace to the Electrical model rather than to this port.

The reason the chain is ported rather than only replayed: v1.5 closes the loop.
The controller derate factor scales the commanded joint torque every step, and
the pack current that follows has to be recomputed through the whole chain,
including the nonlinear copper loss and the peak-torque clip. A fixed current
trace cannot represent that.
"""
import csv
import os

import numpy as np

from .params import P

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TEMPLATE_CSV = os.path.join(DATA_DIR, "fukuchi_young_overground_engineering_template.csv")


def _kt_out():
    """Output-side torque constant, motor Kt reflected through the gearbox."""
    return P["actuator_kt_Nm_per_A"] * P["gear_ratio"] * P["gear_eff_motoring"]


def actuator_dc_power(p_mech, i_q, regen_enabled):
    """DC input power of one actuator [W]. Positive discharges the pack.

    Identical form to actuator_dc_power() nested in simulate_gait_cycle.m.
    """
    p_cu = (i_q ** 2) * P["copper_r_ohm"]
    p_idle = P["driver_idle_W"]
    if p_mech >= 0.0:
        return p_mech / (P["gear_eff_motoring"] * P["inverter_eff"]) + p_cu + p_idle
    if regen_enabled:
        return (p_mech * P["gear_eff_regen"] * P["inverter_eff"]
                * P["regen_conversion_eff"] + p_cu + p_idle)
    return p_cu + p_idle


class GaitChain:
    """Periodic hip and knee load from the Fukuchi template."""

    def __init__(self, mode=None, cadence_spm=None, mass_kg=None,
                 hip_frac=None, knee_frac=None, electronics_W=None,
                 template_csv=TEMPLATE_CSV):
        self.mode = (mode or P["gait_mode"]).lower()
        self.cadence_spm = float(cadence_spm or P["cadence_spm"])
        self.mass_kg = float(mass_kg or P["subject_mass_kg"])
        self.hip_frac = P["hip_assist_frac"] if hip_frac is None else float(hip_frac)
        self.knee_frac = P["knee_assist_frac"] if knee_frac is None else float(knee_frac)
        self.electronics_W = P["electronics_W"] if electronics_W is None else float(electronics_W)
        self.template_csv = template_csv
        self.source = os.path.basename(template_csv)

        rows = []
        with open(template_csv, newline="") as f:
            for row in csv.DictReader(f):
                if row["mode"].strip().lower() == self.mode:
                    rows.append(row)
        if not rows:
            raise ValueError("gait mode %r not present in %s" % (self.mode, template_csv))
        rows.sort(key=lambda r: float(r["phase_pct"]))

        self.phase = np.array([float(r["phase_pct"]) for r in rows]) / 100.0
        hip_ang = np.deg2rad([float(r["hip_angle_deg"]) for r in rows])
        knee_ang = np.deg2rad([float(r["knee_angle_deg"]) for r in rows])
        hip_mom = np.array([float(r["hip_moment_Nm_per_kg"]) for r in rows])
        knee_mom = np.array([float(r["knee_moment_Nm_per_kg"]) for r in rows])

        self.stride_s = 120.0 / self.cadence_spm      # one stride is two steps
        t = self.phase * self.stride_s
        self.hip_omega = np.gradient(hip_ang, t)
        self.knee_omega = np.gradient(knee_ang, t)
        self.hip_cmd = self.hip_frac * hip_mom * self.mass_kg
        self.knee_cmd = self.knee_frac * knee_mom * self.mass_kg

        # Periodic interpolation grid: repeat the first sample at phase 1.0.
        self._xp = np.append(self.phase, 1.0)
        self._tab = {
            "hip_cmd": np.append(self.hip_cmd, self.hip_cmd[0]),
            "knee_cmd": np.append(self.knee_cmd, self.knee_cmd[0]),
            "hip_omega": np.append(self.hip_omega, self.hip_omega[0]),
            "knee_omega": np.append(self.knee_omega, self.knee_omega[0]),
        }

    # ------------------------------------------------------------- sampling
    def at(self, t_s, torque_scale=1.0, regen_enabled=False, assist=None):
        """Load at time t_s with the commanded torque scaled by torque_scale.

        Returns a dict with the DC-bus power and the joint-level diagnostics.
        The assist argument exists for interface compatibility with
        gaitctl.ExoAssistModel and is ignored: this source's assist level is
        the fixed percentage of the healthy moment set in params.
        """
        ph = (t_s / self.stride_s) % 1.0
        hip_cmd = float(np.interp(ph, self._xp, self._tab["hip_cmd"])) * torque_scale
        knee_cmd = float(np.interp(ph, self._xp, self._tab["knee_cmd"])) * torque_scale
        hip_w = float(np.interp(ph, self._xp, self._tab["hip_omega"]))
        knee_w = float(np.interp(ph, self._xp, self._tab["knee_omega"]))

        peak = P["actuator_peak_torque_Nm"]
        hip_tau = min(max(hip_cmd, -peak), peak)
        knee_tau = min(max(knee_cmd, -peak), peak)
        kt = _kt_out()
        hip_iq, knee_iq = hip_tau / kt, knee_tau / kt
        p_dc = (actuator_dc_power(hip_tau * hip_w, hip_iq, regen_enabled)
                + actuator_dc_power(knee_tau * knee_w, knee_iq, regen_enabled)
                + self.electronics_W)
        return {"phase_frac": ph, "phase_pct": 100.0 * ph, "p_dc_W": p_dc,
                "hip_torque_Nm": hip_tau, "knee_torque_Nm": knee_tau,
                "hip_iq_A": hip_iq, "knee_iq_A": knee_iq,
                "clipped": abs(hip_cmd) > peak or abs(knee_cmd) > peak}

    def stride_summary(self, torque_scale=1.0, regen_enabled=False, n=401):
        """Per-stride power and energy at a fixed torque scale."""
        t = np.linspace(0.0, self.stride_s, n)
        p = np.array([self.at(x, torque_scale, regen_enabled)["p_dc_W"] for x in t])
        return {
            "torque_scale": torque_scale,
            "regen_enabled": bool(regen_enabled),
            "stride_s": round(self.stride_s, 4),
            "peak_dc_power_W": round(float(p.max()), 1),
            "min_dc_power_W": round(float(p.min()), 1),
            "mean_dc_power_W": round(float(p.mean()), 1),
            "energy_per_stride_Wh": round(float(np.trapz(p, t) / 3600.0), 5),
            "regen_energy_per_stride_Wh": round(float(-np.trapz(np.minimum(p, 0.0), t) / 3600.0), 5),
            "peak_phase_pct": round(float(100.0 * t[int(np.argmax(p))] / self.stride_s), 1),
        }

    def export_profile(self, path, strides=1, n_per_stride=401, torque_scale=1.0,
                       regen_enabled=False, bus_v=48.0):
        """Write the ported profile as a CSV in the same column contract as
        matlab/export_bms_profile.m, for comparison against the MATLAB export."""
        t = np.linspace(0.0, strides * self.stride_s, strides * n_per_stride)
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t_s", "P_W", "I_A_at_ref_bus", "phase_pct"])
            for x in t:
                s = self.at(x, torque_scale, regen_enabled)
                w.writerow(["%.5f" % x, "%.3f" % s["p_dc_W"],
                            "%.4f" % (s["p_dc_W"] / bus_v), "%.3f" % s["phase_pct"]])
        return path


class GaitCsvSource:
    """Playback of a profile exported from the MATLAB model.

    Required column: t_s. Then either P_W (preferred, the pack current is
    solved against the live pack voltage) or I_A (current played back
    directly, which cannot respond to pack voltage or to a derate).
    """

    def __init__(self, path):
        self.path = path
        t, p, i = [], [], []
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                t.append(float(row["t_s"]))
                if "P_W" in row and row["P_W"] not in (None, ""):
                    p.append(float(row["P_W"]))
                if "I_A" in row and row["I_A"] not in (None, ""):
                    i.append(float(row["I_A"]))
        self.t = np.array(t)
        self.p = np.array(p) if len(p) == len(t) else None
        self.i = np.array(i) if len(i) == len(t) else None
        if self.p is None and self.i is None:
            raise ValueError("%s has neither a P_W nor an I_A column" % path)
        self.kind = "power" if self.p is not None else "current"
        self.duration_s = float(self.t[-1])

    def at(self, t_s, torque_scale=1.0, regen_enabled=False, assist=None):
        x = t_s % self.duration_s if self.duration_s > 0 else 0.0
        if self.kind == "power":
            return {"p_dc_W": float(np.interp(x, self.t, self.p)) * torque_scale,
                    "phase_frac": x / self.duration_s, "phase_pct": 100.0 * x / self.duration_s,
                    "clipped": False}
        return {"i_cmd_A": float(np.interp(x, self.t, self.i)) * torque_scale,
                "phase_frac": x / self.duration_s, "phase_pct": 100.0 * x / self.duration_s,
                "clipped": False}
