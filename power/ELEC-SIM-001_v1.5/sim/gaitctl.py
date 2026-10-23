"""Primary gait control layer: a port of the Electrical team's one-sided
assist model.

Source of record
    Drive: EXO > Electrical > Test Data
        one_sided_battery_current.m   (assist controller + battery current)
        battery_current.m             (simpler per-joint percentage variant)
        PostStroke_Moco_Comparison_Data_Hemi.xml   (201 samples, hemiparetic)
        Healthy_Gait_Comparison_Data.xml           (135 samples, healthy)
    These are the files behind the 3 to 4 A mean battery current quoted on the
    Electrical biweekly sheet of 2026-10-12 and in ELEC-DOC-007 Section 4.

What the control model does
    The exoskeleton sits on the weaker leg. At every sample it asks for the
    torque gap between the weaker leg and the stronger leg, re-timed so the
    two strides line up:
        gap    = tau_strong(shifted) - tau_weak
        ta_req = assist * gap
        ta     = clip(ta_req, +/- tauMax)
    The drivetrain then gives joint mechanical power, motor-side torque, hot
    copper loss and battery power. Braking samples (Pe <= 0) are set to zero
    battery power: the MATLAB model takes no regen credit.

What v1.5 changes, and why
    1. Fixed bus voltage. The MATLAB model divides battery power by a constant
       48 V. A 12S1P pack is 50.4 V full, 43.2 V nominal and sags 0.18 ohm x I
       under load, so the real battery current is higher than the MATLAB
       figure at low SOC and at high current. v1.5 solves the current against
       the live pack terminal voltage instead and reports both.
    2. Discarded braking energy. Pb = 0 where Pe <= 0 hides the question of
       where that energy goes. The regen module makes it explicit: what the
       pack will accept, and what has to be dissipated (PD-14).
    3. No auxiliary load. The Jetson, Teensy and sensors (45 W nominal) are
       not in the MATLAB model but are on the pack. v1.5 adds them.
    4. No protection layer and no controller. v1.5 runs the assist sweep
       through the BMS state machine and the telemetry consumer, so the assist
       level is limited by what the pack and the BMS trip settings allow.

Anything this module computes that the MATLAB model also computes shall agree
with it. If the two disagree, the MATLAB model is authoritative and this port
is wrong.
"""
import os
import xml.etree.ElementTree as ET

import numpy as np

from .params import P

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HEMI_XML = os.path.join(DATA_DIR, "PostStroke_Moco_Comparison_Data_Hemi.xml")
HEALTHY_XML = os.path.join(DATA_DIR, "Healthy_Gait_Comparison_Data.xml")

JOINTS = ("Hip", "Knee")
SIDES = ("Left", "Right")


# --------------------------------------------------------------------- input
class MocoGaitData:
    """Reader for the Comparison_Data XML files in Electrical > Test Data.

    Layout (confirmed against both files):
        <Root><Metadata>...</Metadata>
          <Signals>
            <Sample index="1" time_s="0.45">
              <JointMoments_Nm><RightHip/><RightKnee/><LeftHip/><LeftKnee/></JointMoments_Nm>
              <AngularVelocities_rad_s><RightHip/>...</AngularVelocities_rad_s>
            </Sample> ...
    """

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        root = ET.parse(path).getroot()
        self.metadata = {c.tag: (c.text or "").strip() for c in (root.find("Metadata") or [])}
        self.condition = root.get("condition", "")

        samples = root.findall("./Signals/Sample")
        if not samples:
            raise ValueError("%s contains no Signals/Sample elements" % path)

        t, mom, vel = [], [], []
        for s in samples:
            t.append(float(s.get("time_s")))
            m = s.find("JointMoments_Nm")
            w = s.find("AngularVelocities_rad_s")
            mom.append([float(m.find(side + j).text) for side in SIDES for j in JOINTS])
            vel.append([float(w.find(side + j).text) for side in SIDES for j in JOINTS])

        self.t = np.asarray(t)
        # Columns: Left Hip, Left Knee, Right Hip, Right Knee.
        self.tau = np.asarray(mom)
        self.omega = np.asarray(vel)

        # The exported cycle repeats its first sample at the end. Drop it so a
        # circular shift of one leg wraps cleanly (same test as the MATLAB).
        if np.max(np.abs(self.tau[-1] - self.tau[0])) < 1e-6:
            self.t = self.t[:-1]
            self.tau = self.tau[:-1]
            self.omega = self.omega[:-1]

        self.n = len(self.t)
        self.duration_s = float(self.t[-1] - self.t[0]) * self.n / max(self.n - 1, 1)
        self.phase_pct = 100.0 * np.arange(self.n) / self.n

    def side(self, which):
        """(tau, omega) for one side as [:, [hip, knee]]."""
        k = 0 if which == "Left" else 2
        return self.tau[:, k:k + 2], self.omega[:, k:k + 2]


def synthetic_hemi_data(n=201, duration_s=1.1, weak_scale=0.55, seed=3):
    """SYNTHETIC stand-in used only when the Drive XML files are not present.

    It is a scaled, phase-shifted sine pair. It exercises the pipeline and
    nothing else. No result produced from it may be reported. Replace it by
    copying the two XML files from EXO > Electrical > Test Data into data/.
    """
    rng = np.random.default_rng(seed)
    t = np.linspace(0.0, duration_s, n, endpoint=False)
    ph = 2 * np.pi * t / duration_s
    strong_hip = 45.0 * np.sin(ph) - 12.0 * np.sin(2 * ph)
    strong_knee = -38.0 * np.sin(ph + 0.6) - 15.0 * np.sin(2 * ph + 0.3)
    w_hip = 3.0 * np.cos(ph)
    w_knee = 5.0 * np.cos(ph + 0.6)

    obj = MocoGaitData.__new__(MocoGaitData)
    obj.path = "<synthetic>"
    obj.name = "SYNTHETIC_hemi_stand_in"
    obj.metadata = {"Note": "synthetic, not Electrical > Test Data"}
    obj.condition = "synthetic"
    obj.t = t
    half = n // 2
    weak_hip = weak_scale * np.roll(strong_hip, half) + rng.normal(0, 0.4, n)
    weak_knee = weak_scale * np.roll(strong_knee, half) + rng.normal(0, 0.4, n)
    obj.tau = np.column_stack([weak_hip, weak_knee, strong_hip, strong_knee])
    obj.omega = np.column_stack([np.roll(w_hip, half), np.roll(w_knee, half), w_hip, w_knee])
    obj.n = n
    obj.duration_s = duration_s
    obj.phase_pct = 100.0 * np.arange(n) / n
    return obj


def load_gait_data(path=None):
    """Preferred data file, else the healthy file, else the synthetic stand-in."""
    for candidate in ([path] if path else []) + [HEMI_XML, HEALTHY_XML]:
        if candidate and os.path.exists(candidate):
            return MocoGaitData(candidate), True
    return synthetic_hemi_data(), False


# ---------------------------------------------------------------- controller
class ExoAssistModel:
    """Port of exoModel() from one_sided_battery_current.m."""

    def __init__(self, data, assist=None, weak_side=None, velocity_from=None,
                 tau_max=None, hot_factor=None, phase_shift_pct=None,
                 include_aux=None, aux_W=None):
        self.data = data
        self.assist = P["ctl_assist"] if assist is None else float(assist)
        self.tau_max = P["ctl_tau_max_Nm"] if tau_max is None else float(tau_max)
        self.hot = P["ctl_hot_factor"] if hot_factor is None else float(hot_factor)
        self.velocity_from = velocity_from or P["ctl_velocity_from"]
        self.include_aux = P["ctl_include_aux_load"] if include_aux is None else bool(include_aux)
        self.aux_W = P["electronics_W"] if aux_W is None else float(aux_W)

        want = weak_side or P["ctl_weak_side"]
        if want == "auto":
            l_tau, _ = data.side("Left")
            r_tau, _ = data.side("Right")
            want = "Left" if np.sqrt(np.mean(l_tau ** 2)) < np.sqrt(np.mean(r_tau ** 2)) else "Right"
        self.weak_side = want
        self.strong_side = "Right" if want == "Left" else "Left"

        self.tau_w, self.w_weak = data.side(self.weak_side)
        tau_s, w_strong = data.side(self.strong_side)

        # Align the two strides. They sit about half a cycle apart.
        n = data.n
        if phase_shift_pct is None:
            score = np.zeros(n)
            for k in range(n):
                shifted = np.roll(w_strong, k, axis=0)
                score[k] = (np.corrcoef(shifted[:, 0], self.w_weak[:, 0])[0, 1]
                            + np.corrcoef(shifted[:, 1], self.w_weak[:, 1])[0, 1])
            shift = int(np.nanargmax(score))
        else:
            shift = int(round(phase_shift_pct / 100.0 * n))
        self.shift = shift
        self.shift_pct = 100.0 * shift / n

        self.tau_target = np.roll(tau_s, shift, axis=0)
        self.w_target = np.roll(w_strong, shift, axis=0)
        self.omega = self.w_target if self.velocity_from == "strong" else self.w_weak

        self.cycle_s = float(data.duration_s)
        self.phase_pct = data.phase_pct

    # ------------------------------------------------------------- per cycle
    def cycle(self, assist=None, torque_scale=1.0, regen_enabled=False):
        """Whole-cycle arrays at one assist level. Port of exoModel()."""
        a = self.assist if assist is None else float(assist)
        n9, eg, ec = P["ctl_gear_ratio"], P["ctl_gear_eff"], P["ctl_ctrl_eff"]
        kt, km = P["ctl_kt_Nm_per_A"], P["ctl_km_Nm_per_sqrtW"]

        gap = self.tau_target - self.tau_w
        ta_req = a * torque_scale * gap
        ta = np.clip(ta_req, -self.tau_max, self.tau_max)

        p_mech = ta * self.omega
        drive = p_mech >= 0.0

        tm = np.where(drive, np.abs(ta) / (n9 * eg), np.abs(ta) * eg / n9)
        p_rotor = np.where(drive, p_mech / eg, p_mech * eg)
        p_cu = self.hot * (tm / km) ** 2
        p_e = p_rotor + p_cu

        # MATLAB behaviour: braking samples contribute no battery power.
        p_b_matlab = np.where(p_e > 0.0, p_e / ec, 0.0)
        if regen_enabled:
            # v1.5: net-negative electrical power returns to the bus through
            # the controller, reduced by the controller and conversion losses.
            p_b = np.where(p_e > 0.0, p_e / ec,
                           p_e * ec * P["regen_conversion_eff"])
        else:
            p_b = p_b_matlab

        aux = self.aux_W if self.include_aux else 0.0
        # Braking power at the bus before the auxiliary load is netted off.
        # The pack only sees regeneration when braking exceeds the auxiliary
        # load, so both figures are needed to argue PD-14.
        p_drivetrain = p_b.sum(axis=1)
        remaining = self.tau_target - (self.tau_w + ta)
        with np.errstate(invalid="ignore", divide="ignore"):
            gap_closed = 1.0 - np.sqrt(np.mean(remaining ** 2, axis=0)) / np.sqrt(np.mean(gap ** 2, axis=0))

        return {
            "assist": a, "torque_scale": torque_scale,
            "phase_pct": self.phase_pct,
            "exo_torque_Nm": ta,
            "motor_torque_Nm": tm,
            "phase_current_A": tm / kt,
            "p_joint_W": p_b,                       # per joint, bus side
            "p_bus_W": p_b.sum(axis=1) + aux,       # total DC-bus power
            "p_drivetrain_W": p_drivetrain,         # bus power before the aux load
            "p_bus_matlab_W": p_b_matlab.sum(axis=1),   # exactly the MATLAB figure
            "i_fixed_bus_A": p_b_matlab.sum(axis=1) / P["ctl_bus_V_fixed"],
            "gap_closed": gap_closed,
            "saturated_pct": 100.0 * np.mean(np.abs(ta_req) > self.tau_max, axis=0),
            "aux_W": aux,
        }

    def braking_budget(self, assist=None):
        """Braking energy per gait cycle, with regeneration credited.

        Three figures, because they answer different questions:
            drivetrain   what the actuators send back to the bus
            after_aux    what is left after the auxiliary load consumes it
            per_minute   the rate, for sizing a clamp (PD-14)
        """
        c = self.cycle(assist=assist, regen_enabled=True)
        dt = self.cycle_s / max(self.data.n, 1)
        p_dt = c["p_drivetrain_W"]
        p_bus = c["p_bus_W"]
        e_drive = float(-np.sum(np.minimum(p_dt, 0.0)) * dt / 3600.0)
        e_bus = float(-np.sum(np.minimum(p_bus, 0.0)) * dt / 3600.0)
        cycles_per_min = 60.0 / self.cycle_s
        return {
            "assist": self.assist if assist is None else assist,
            "aux_load_W": c["aux_W"],
            "braking_energy_per_cycle_Wh_at_drivetrain": round(e_drive, 5),
            "braking_energy_per_cycle_Wh_reaching_the_pack": round(e_bus, 5),
            "absorbed_by_aux_load_Wh": round(max(e_drive - e_bus, 0.0), 5),
            "peak_braking_power_W_at_drivetrain": round(float(-np.min(p_dt)), 1),
            "peak_braking_power_W_reaching_the_pack": round(float(max(-np.min(p_bus), 0.0)), 1),
            "braking_energy_per_minute_Wh": round(e_bus * cycles_per_min, 4),
            "cycles_per_minute": round(cycles_per_min, 1),
            "fraction_of_cycle_braking_at_the_pack": round(float(np.mean(p_bus < 0.0)), 4),
        }

    def summary(self, assist=None, regen_enabled=False):
        c = self.cycle(assist=assist, regen_enabled=regen_enabled)
        i_fixed = c["i_fixed_bus_A"]
        return {
            "assist": round(c["assist"], 3),
            "weak_side": self.weak_side,
            "strong_side": self.strong_side,
            "strong_leg_shift_pct": round(self.shift_pct, 1),
            "cycle_s": round(self.cycle_s, 4),
            "peak_exo_torque_Nm": [round(float(x), 2) for x in np.max(np.abs(c["exo_torque_Nm"]), axis=0)],
            "at_torque_limit_pct": [round(float(x), 1) for x in c["saturated_pct"]],
            "gap_closed_pct": [round(100.0 * float(x), 1) for x in c["gap_closed"]],
            "peak_phase_current_A": [round(float(x), 2) for x in np.max(c["phase_current_A"], axis=0)],
            "rms_phase_current_A": [round(float(np.sqrt(np.mean(x ** 2))), 2)
                                    for x in c["phase_current_A"].T],
            # Reported exactly as one_sided_battery_current.m reports it.
            "matlab_peak_battery_A_at_48V": round(float(i_fixed.max()), 2),
            "matlab_mean_battery_A_at_48V": round(float(i_fixed.mean()), 2),
            "matlab_rms_battery_A_at_48V": round(float(np.sqrt(np.mean(i_fixed ** 2))), 2),
            "peak_bus_power_W": round(float(c["p_bus_W"].max()), 1),
            "mean_bus_power_W": round(float(c["p_bus_W"].mean()), 1),
            "min_bus_power_W": round(float(c["p_bus_W"].min()), 1),
            "aux_load_W": c["aux_W"],
        }

    # -------------------------------------------------------- time sampling
    def at(self, t_s, torque_scale=1.0, regen_enabled=False, assist=None):
        """DC-bus power at time t_s, with the commanded torque scaled.

        torque_scale is the controller derate factor. It multiplies the
        commanded assist torque before the clip, so the copper loss and the
        saturation behaviour both follow it.
        """
        a = self.assist if assist is None else float(assist)
        n = self.data.n
        x = (t_s % self.cycle_s) / self.cycle_s * n
        i0 = int(np.floor(x)) % n
        i1 = (i0 + 1) % n
        f = x - np.floor(x)

        n9, eg, ec = P["ctl_gear_ratio"], P["ctl_gear_eff"], P["ctl_ctrl_eff"]
        km = P["ctl_km_Nm_per_sqrtW"]
        gap = (1 - f) * (self.tau_target[i0] - self.tau_w[i0]) + f * (self.tau_target[i1] - self.tau_w[i1])
        omega = (1 - f) * self.omega[i0] + f * self.omega[i1]

        ta = np.clip(a * torque_scale * gap, -self.tau_max, self.tau_max)
        p_mech = ta * omega
        drive = p_mech >= 0.0
        tm = np.where(drive, np.abs(ta) / (n9 * eg), np.abs(ta) * eg / n9)
        p_rotor = np.where(drive, p_mech / eg, p_mech * eg)
        p_e = p_rotor + self.hot * (tm / km) ** 2
        if regen_enabled:
            p_b = np.where(p_e > 0.0, p_e / ec, p_e * ec * P["regen_conversion_eff"])
        else:
            p_b = np.where(p_e > 0.0, p_e / ec, 0.0)

        aux = self.aux_W if self.include_aux else 0.0
        return {"p_dc_W": float(p_b.sum() + aux),
                "phase_pct": 100.0 * (t_s % self.cycle_s) / self.cycle_s,
                "hip_torque_Nm": float(ta[0]), "knee_torque_Nm": float(ta[1]),
                "phase_current_A": float(np.max(tm) / P["ctl_kt_Nm_per_A"]),
                "clipped": bool(np.any(np.abs(a * torque_scale * gap) > self.tau_max))}
