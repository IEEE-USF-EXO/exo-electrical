"""Scenario set and the two parameter studies.

S1 to S9 carry over from v0.1 so the v0.1 results stay comparable. S1, S7 and
S9 are now driven by the gait control model instead of a synthetic pulse, and
S1 and S7 run closed loop. S10 to S14 are new in v1.5.

The two studies are the point of the integration:

    assist_ceiling_study    The control model's assist level is swept from 0
                            to 100%, exactly as the sweep at the bottom of
                            one_sided_battery_current.m does, but each level
                            is run through the pack and the BMS. It returns
                            the highest assist level that does not trip, with
                            the binding protection named. This is a control
                            limit that neither model finds on its own.

    bus_voltage_study       The same cycle evaluated against the fixed 48 V of
                            the MATLAB model and against the live pack
                            voltage at several states of charge, to quantify
                            how much the fixed-voltage assumption understates
                            battery current.
"""
import numpy as np

from . import surge as sg
from .params import P
from .runner import Scenario, run


def build(source, regen_source=None):
    """The scenario list. source is the gait control model."""
    cycle = getattr(source, "cycle_s", 1.0)
    rs = regen_source if regen_source is not None else source
    return [
        Scenario("S1", "Nominal gait, closed loop, assist at the configured level",
                 30.0, source=source, soc0=0.95),
        Scenario("S2", "Sustained dual-actuator demand of 56 A on top of gait",
                 6.0, source=source, soc0=1.0,
                 surge_fn=sg.actuator_surge(1.0, 10.0)),
        Scenario("S3", "Bolted fault on the motor bus, 150 A",
                 1.0, source=source, soc0=1.0, surge_fn=sg.short_circuit(0.2)),
        Scenario("S4", "Charge step of 10 A into a pack at 95% SOC",
                 6.0, current_fn=lambda t: -10.0 if t >= 1.0 else 0.0,
                 soc0=0.95, regen_enabled=True, closed_loop=False),
        Scenario("S5", "Charge at 4.5 A with one cell 12% high, balancing active",
                 300.0, current_fn=lambda t: -4.5, soc0=0.80, offsets={6: 0.12},
                 regen_enabled=True, closed_loop=False),
        Scenario("S6", "Thermal ramp at 3.5 A to the over-temperature trip",
                 80.0, current_fn=lambda t: 3.5, soc0=0.9,
                 temp_fn=lambda t: 25.0 + 0.5 * t, closed_loop=False),
        Scenario("S7", "Telemetry dropout for 2 s during gait, closed loop",
                 20.0, source=source, soc0=0.9, comm_drop=(8.0, 10.0),
                 run_to_end=True),
        Scenario("S9", "Cold charge at minus 5 C, charge inhibit expected",
                 5.0, current_fn=lambda t: -4.5, soc0=0.5,
                 temp_fn=lambda t: -5.0, regen_enabled=True, closed_loop=False),

        # ------------------------------------------------------- new in v1.5
        Scenario("S10", "Gait with a dual-actuator peak once per stride, 0.4 s each",
                 6 * cycle, source=source, soc0=0.9,
                 surge_fn=sg.repeating_actuator_surge(cycle, 0.4, phase_offset=0.5 * cycle)),
        Scenario("S11", "Gait with regeneration credited, pack at 98% SOC, no clamp",
                 20.0, source=rs, soc0=0.98, regen_enabled=True, clamp_present=False),
        Scenario("S12", "Gait with regeneration credited and the clamp fitted (PD-14 option A)",
                 20.0, source=rs, soc0=0.98, regen_enabled=True, clamp_present=True),
        Scenario("S13", "Gait at 12% SOC: sag, undervoltage margin and derate behaviour",
                 40.0, source=source, soc0=0.12, run_to_end=False),
        Scenario("S14", "Gait with regeneration credited at 40% SOC, pack has headroom",
                 20.0, source=rs, soc0=0.40, regen_enabled=True, clamp_present=False),
    ]


def run_all(source, regen_source=None):
    results, traces = [], {}
    for sc in build(source, regen_source):
        r, tr = run(sc)
        results.append(r)
        traces[sc.name] = tr
    return results, traces


# --------------------------------------------------------------- studies
def assist_ceiling_study(source, levels=None, soc0=0.9, cycles=4, regen_enabled=False):
    """Sweep the assist level through the pack and the BMS.

    The MATLAB sweep reports peak and mean battery current against assist
    level. This one additionally reports whether the protection acts, and at
    which level it first does.
    """
    if levels is None:
        levels = np.round(np.arange(0.0, 1.0001, 0.05), 3)
    rows = []
    for a in levels:
        sc = Scenario("A%.0f" % (100 * a),
                      "assist sweep point", cycles * source.cycle_s,
                      source=source, soc0=soc0, assist=float(a),
                      regen_enabled=regen_enabled, run_to_end=True)
        r, tr = run(sc)
        m = source.summary(assist=float(a), regen_enabled=regen_enabled)
        rows.append({
            "assist_pct": int(round(100 * a)),
            "matlab_peak_A_at_48V": m["matlab_peak_battery_A_at_48V"],
            "matlab_mean_A_at_48V": m["matlab_mean_battery_A_at_48V"],
            "coupled_peak_A": r["peak_current_A"],
            "coupled_mean_A": round(float(np.mean(np.maximum(tr["i"], 0.0))), 2),
            "min_pack_V": r["min_pack_V"],
            "peak_phase_current_A": max(m["peak_phase_current_A"]),
            "knee_rms_phase_A": m["rms_phase_current_A"][1],
            "gap_closed_pct": m["gap_closed_pct"],
            "at_torque_limit_pct": m["at_torque_limit_pct"],
            "tripped": r["tripped"],
            "fault": r["fault"],
            "min_torque_scale": r["min_torque_scale"],
        })
    clean = [r for r in rows if not r["tripped"]]
    ceiling = max((r["assist_pct"] for r in clean), default=None)
    first_trip = next((r for r in rows if r["tripped"]), None)
    return {
        "soc_pct": int(100 * soc0),
        "cycles_per_point": cycles,
        "regen_enabled": regen_enabled,
        "rows": rows,
        "highest_assist_without_trip_pct": ceiling,
        "first_tripping_assist_pct": None if first_trip is None else first_trip["assist_pct"],
        "first_trip_fault": None if first_trip is None else first_trip["fault"],
        "actuator_rated_phase_current_A": 12.0,
        "note": ("A point marked not tripped is limited by the actuator and by the thermal "
                 "rating, not by the pack. Compare knee_rms_phase_A against the 12 A rated "
                 "phase current before reading an assist level as available."),
    }


def bus_voltage_study(source, soc_values=(1.0, 0.8, 0.5, 0.2, 0.1), assist=None):
    """Fixed 48 V against the live pack voltage, same cycle.

    The MATLAB model divides bus power by a constant 48 V. This compares that
    with the current the same power actually draws from a 12S1P pack.
    """
    from .pack import Pack

    c = source.cycle(assist=assist)
    p_bus = c["p_bus_W"]
    p_matlab = c["p_bus_matlab_W"]
    rows = []
    for soc in soc_values:
        pack = Pack(soc0=soc, seed=0)
        i_live, i_live_no_aux = [], []
        for p, p_na in zip(p_bus, p_matlab):
            i, feasible = pack.current_for_power(float(p))
            i_live.append(i if feasible else float("nan"))
            i_na, ok = pack.current_for_power(float(p_na))
            i_live_no_aux.append(i_na if ok else float("nan"))
        i_live = np.asarray(i_live)
        i_live_no_aux = np.asarray(i_live_no_aux)
        i_fixed = p_matlab / P["ctl_bus_V_fixed"]
        rows.append({
            "soc_pct": int(round(100 * soc)),
            "open_circuit_pack_V": round(pack.source_v(), 2),
            "matlab_peak_A_at_48V": round(float(i_fixed.max()), 2),
            # Voltage effect alone: same power as the MATLAB model carries,
            # no auxiliary load, solved against the live pack voltage.
            "coupled_peak_A_voltage_effect_only": round(float(np.nanmax(i_live_no_aux)), 2),
            "coupled_peak_A": round(float(np.nanmax(i_live)), 2),
            "peak_delta_A": round(float(np.nanmax(i_live) - i_fixed.max()), 2),
            "peak_delta_pct": round(100.0 * (float(np.nanmax(i_live)) / max(i_fixed.max(), 1e-9) - 1.0), 1),
            "matlab_mean_A_at_48V": round(float(i_fixed.mean()), 2),
            "coupled_mean_A": round(float(np.nanmean(i_live)), 2),
            "pack_V_at_peak_current": round(pack.pack_v(float(np.nanmax(i_live))), 2),
        })
    return {"assist": source.assist if assist is None else assist,
            "aux_load_included_W": c["aux_W"],
            "rows": rows,
            "note": ("The coupled column includes the auxiliary load, which the MATLAB model "
                     "does not carry. Both effects push battery current up.")}
