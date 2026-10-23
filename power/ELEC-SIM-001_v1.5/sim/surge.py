"""Current surge module.

v0.1 applied surges as bare step currents with the gait load switched off.
v1.5 superimposes them on the running gait load, because the question that
matters is not whether 56 A trips the pack but whether a surge arriving on top
of an ordinary stride does.

Three surge classes:

    inrush        Closing the motor-bus contactor onto the drive bulk
                  capacitance. Peak current is set by the series resistance,
                  and the decay time constant is R*C. With no precharge
                  resistor the peak is pack voltage over the pack and harness
                  resistance alone, which is hundreds of amperes for a few
                  hundred microseconds. The short-circuit delay is 10 ms, so
                  the BMS does not see it: this is a connector, FET and
                  capacitor stress question, not a protection question. That
                  is the argument for the precharge resistor, which is listed
                  as Not chosen on the BOM (RK-03).

    actuator      Both AK80-9 actuators commanded to peak phase current at
                  once: 2 x 28 A = 56 A at the pack (Technical Baseline 6.1,
                  BOM worst case). This exceeds the 45 A cell continuous
                  rating by 11 A, which is risk RK-01. Rise time is the
                  driver current loop, not the mechanics.

    short         A bolted fault on the motor bus.

A surge is a callable (t) -> additional pack current in amperes, added to the
current the gait layer and the pack solve produce.
"""
import numpy as np

from .params import P


def no_surge():
    return lambda t: 0.0


def actuator_surge(t_start, duration, amps=None, rise_s=None):
    """Both actuators to peak current, with a finite rise."""
    a = P["surge_dual_peak_A"] if amps is None else float(amps)
    rise = P["surge_rise_s"] if rise_s is None else float(rise_s)

    def f(t):
        if t < t_start or t > t_start + duration:
            return 0.0
        ramp = min(1.0, (t - t_start) / max(rise, 1e-9))
        return a * ramp

    return f


def repeating_actuator_surge(period, duration, phase_offset=0.0, amps=None):
    """A peak-torque demand once per gait cycle, for example a stumble
    recovery or a stair step repeated every stride."""
    a = P["surge_dual_peak_A"] if amps is None else float(amps)

    def f(t):
        x = (t - phase_offset) % period
        return a if 0.0 <= x <= duration else 0.0

    return f


def short_circuit(t_start, amps=None):
    a = 150.0 if amps is None else float(amps)
    return lambda t: a if t >= t_start else 0.0


def inrush_analysis(pack_v, pack_r, with_precharge=True):
    """Closed-form inrush into the bus capacitance. No time stepping: the
    event is shorter than the simulation step when no precharge is fitted.
    """
    c_f = P["bus_capacitance_uF"] * 1e-6
    r = pack_r + (P["precharge_r_ohm"] if with_precharge else 0.0)
    i_peak = pack_v / r
    tau = r * c_f
    energy_J = 0.5 * c_f * pack_v ** 2
    t_to_95 = 3.0 * tau
    return {
        "precharge_fitted": bool(with_precharge),
        "series_resistance_ohm": round(r, 4),
        "peak_inrush_A": round(i_peak, 1),
        "time_constant_ms": round(tau * 1000.0, 4),
        "time_to_95_pct_ms": round(t_to_95 * 1000.0, 3),
        "energy_into_capacitance_J": round(energy_J, 3),
        "resistor_energy_per_close_J": round(energy_J, 3),
        "exceeds_sc_setting": bool(i_peak > P["sc_trip_A"]),
        "sc_delay_ms": P["sc_delay_s"] * 1000.0,
        "bms_would_trip": bool(i_peak > P["sc_trip_A"] and t_to_95 > P["sc_delay_s"]),
        "note": ("The surge is far shorter than the 10 ms short-circuit delay, so the BMS does "
                 "not act on it. Rate the contactor, connectors and FETs for the peak, or fit "
                 "the precharge resistor."),
    }


def stacked_worst_case(gait_peak_A):
    """Gait load and a simultaneous dual-actuator peak, against the settings."""
    total = gait_peak_A + P["surge_dual_peak_A"]
    return {
        "gait_peak_A": round(gait_peak_A, 2),
        "actuator_surge_A": P["surge_dual_peak_A"],
        "stacked_peak_A": round(total, 2),
        "ocp_setting_A": P["ocp_dischg_A"],
        "ocp_delay_s": P["ocp_dischg_delay_s"],
        "sc_setting_A": P["sc_trip_A"],
        "sc_delay_s": P["sc_delay_s"],
        "over_cell_continuous_A": round(total - P["cell_i_cont_A"], 2),
        "c_rate": round(total / P["cell_capacity_Ah"], 2),
        "trips_sc_if_sustained": bool(total > P["sc_trip_A"]),
        "trips_ocp_if_sustained": bool(total > P["ocp_dischg_A"]),
    }


def sustained_limit_A():
    """Longest-lasting current that never trips either current protection."""
    return min(P["ocp_dischg_A"], P["sc_trip_A"])


def max_pulse_duration_s(amps):
    """How long a pulse of this amplitude may last before a protection acts."""
    if amps > P["sc_trip_A"]:
        return P["sc_delay_s"]
    if amps > P["ocp_dischg_A"]:
        return P["ocp_dischg_delay_s"]
    return np.inf
