#!/usr/bin/env python3
"""ELEC-SIM-001 v1.5 entry point.

Integrated run of the Electrical gait control model, the BMS protection state
machine, the surge module and the regeneration module against the EXO Phase 1
12S1P pack.

Usage
    python run_sim.py [--outdir results] [--data PATH_TO_XML]
                      [--assist 1.0] [--soc 0.9] [--no-figures]

Data
    The authoritative gait input is PostStroke_Moco_Comparison_Data_Hemi.xml
    from Drive, EXO > Electrical > Test Data. Copy it (and
    Healthy_Gait_Comparison_Data.xml) into data/ before producing any result
    that will be reported. Without it the run falls back to a synthetic
    stand-in and marks every output as not reportable.
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sim import VERSION
from sim import gaitctl, regen as regen_mod, scenarios, surge as surge_mod
from sim.pack import OCV_INTERP, Pack
from sim.params import P, table_for_json, unverified_keys

INK, BLUE, ORANGE, GREY, GREEN = "#0b0b0b", "#2a78d6", "#eb6834", "#8a8a85", "#2e8b57"


def derived_quantities(model, data_is_real):
    n_s = P["n_series"]
    pack = Pack(soc0=1.0, seed=0)
    summary = model.summary()
    stacked = surge_mod.stacked_worst_case(summary["matlab_peak_battery_A_at_48V"])
    return {
        "pack_nominal_V": round(n_s * P["cell_v_nom"], 1),
        "pack_full_V": round(n_s * P["cell_v_max"], 1),
        "pack_cutoff_V": round(n_s * P["cell_v_cutoff"], 1),
        "pack_energy_Wh": round(n_s * P["cell_v_nom"] * P["cell_capacity_Ah"], 1),
        "pack_dcir_ohm": round(n_s * P["cell_dcir_ohm"] + P["pack_extra_r_ohm"], 3),
        "sag_at_56A_V": round(P["surge_dual_peak_A"] * (n_s * P["cell_dcir_ohm"] + P["pack_extra_r_ohm"]), 2),
        "required_C_for_56A": round(P["surge_dual_peak_A"] / P["cell_capacity_Ah"], 1),
        "peak_over_cell_cont_A": round(P["surge_dual_peak_A"] - P["cell_i_cont_A"], 1),
        "ocv_interpolation": OCV_INTERP,
        "gait_data_file": model.data.name,
        "gait_data_is_authoritative": bool(data_is_real),
        "gait_cycle_s": round(model.cycle_s, 4),
        "weak_side": model.weak_side,
        "strong_leg_shift_pct": round(model.shift_pct, 1),
        "runtime_h_at_mean_current": round(
            P["cell_capacity_Ah"] / max(summary["matlab_mean_battery_A_at_48V"], 1e-9), 2),
        "stacked_worst_case": stacked,
        "sustained_current_limit_A": surge_mod.sustained_limit_A(),
        "inrush_with_precharge": surge_mod.inrush_analysis(pack.source_v(), pack.pack_r(), True),
        "inrush_without_precharge": surge_mod.inrush_analysis(pack.source_v(), pack.pack_r(), False),
    }


def make_figures(outdir, model, results, traces, sweep, bus_study, envelope, budget):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "axes.edgecolor": GREY, "axes.labelcolor": INK,
                         "xtick.color": INK, "ytick.color": INK, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e1",
                         "grid.linewidth": 0.6, "axes.facecolor": "#fcfcfb",
                         "figure.facecolor": "#fcfcfb"})
    by_name = {r["scenario"]: r for r in results}

    # ------------------------------------------------------------- figure 1
    fig, ax = plt.subplots(2, 2, figsize=(11, 7.2))

    a = ax[0, 0]
    tr = traces["S1"]
    a.plot(tr["t"], tr["i"], color=ORANGE, lw=1.2)
    a.set_xlim(0, min(6.0, tr["t"][-1]))
    a.set_xlabel("Time (s)")
    a.set_ylabel("Pack current (A)")
    a.set_title("S1 gait control model driving the pack, closed loop")
    a.text(0.02, 0.95, "peak %.1f A, mean %.2f A" % (by_name["S1"]["peak_current_A"],
                                                     float(np.mean(np.maximum(tr["i"], 0)))),
           transform=a.transAxes, va="top", fontsize=8, color=INK,
           bbox=dict(fc="#fcfcfb", ec="none", pad=1.5))

    a = ax[0, 1]
    tr = traces["S2"]
    a.plot(tr["t"], tr["i"], color=ORANGE, lw=1.4)
    a.axhline(P["ocp_dischg_A"], color=GREY, ls="--", lw=1)
    a.text(0.02, P["ocp_dischg_A"] + 1.5, "OCP 45 A, 1.0 s delay", fontsize=8, color=INK)
    if by_name["S2"]["t_trip_s"]:
        a.axvline(by_name["S2"]["t_trip_s"], color=BLUE, lw=1.2)
        a.text(by_name["S2"]["t_trip_s"] - 0.05, 0.75 * max(tr["i"].max(), 1),
               "trip %.2f s" % by_name["S2"]["t_trip_s"], ha="right", fontsize=8, color=INK)
    a.set_title("S2 dual-actuator 56 A on top of gait")
    a.set_xlabel("Time (s)")
    a.set_ylabel("Pack current (A)")

    a = ax[1, 0]
    temps = sorted({r["temp_C"] for r in envelope})
    socs = sorted({r["soc_pct"] for r in envelope})
    grid = np.array([[next(r["max_regen_A"] for r in envelope
                           if r["soc_pct"] == s and r["temp_C"] == t) for t in temps]
                     for s in socs])
    im = a.imshow(grid, aspect="auto", origin="lower", cmap="viridis")
    a.set_xticks(range(len(temps)))
    a.set_xticklabels(["%g" % t for t in temps])
    a.set_yticks(range(len(socs)))
    a.set_yticklabels(socs)
    a.set_xlabel("Pack temperature (C)")
    a.set_ylabel("State of charge (%)")
    a.set_title("Regen acceptance envelope (A)")
    a.grid(False)
    for i in range(len(socs)):
        for j in range(len(temps)):
            a.text(j, i, "%.0f" % grid[i, j], ha="center", va="center", fontsize=7,
                   color="white" if grid[i, j] < grid.max() * 0.6 else "black")
    fig.colorbar(im, ax=a, fraction=0.046, pad=0.04)

    a = ax[1, 1]
    tr = traces["S5"]
    a.plot(tr["t"], tr["vmax"], color=ORANGE, lw=1.4, label="Highest cell")
    a.plot(tr["t"], tr["vmin"], color=BLUE, lw=1.4, label="Lowest cell")
    a.axhline(P["ovp_trip_V"], color=GREY, ls="--", lw=1)
    a.text(0.5, P["ovp_trip_V"] + 0.004, "cell OVP trip 4.20 V", fontsize=8, color=INK)
    a.set_title("S5 charge with one high cell: %s" % by_name["S5"]["fault"].lower().replace("_", " "))
    a.set_xlabel("Time (s)")
    a.set_ylabel("Cell voltage (V)")
    a.legend(frameon=False, loc="lower right")

    fig.suptitle("ELEC-SIM-001 v1.5 protection overview. Parameters are PROPOSED or ASSUMED; "
                 "see the results JSON for the source of every number.", fontsize=10, color=INK)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(os.path.join(outdir, "ELEC-SIM-001_Overview_v1.5.png"), dpi=140)
    plt.close(fig)

    # ------------------------------------------------------------- figure 2
    fig, ax = plt.subplots(2, 2, figsize=(11, 7.2))

    a = ax[0, 0]
    rows = sweep["rows"]
    x = [r["assist_pct"] for r in rows]
    a.plot(x, [r["matlab_peak_A_at_48V"] for r in rows], color=GREY, lw=1.6,
           label="MATLAB model, fixed 48 V")
    a.plot(x, [r["coupled_peak_A"] for r in rows], color=ORANGE, lw=1.8,
           label="Coupled to pack and BMS")
    a.axhline(P["ocp_dischg_A"], color=BLUE, ls="--", lw=1)
    a.text(1, P["ocp_dischg_A"] + 1, "OCP 45 A", fontsize=8, color=INK)
    trip = [r for r in rows if r["tripped"]]
    if trip:
        a.axvline(trip[0]["assist_pct"], color=BLUE, lw=1.2)
        a.text(trip[0]["assist_pct"] - 1, a.get_ylim()[1] * 0.6,
               "first trip at %d%%" % trip[0]["assist_pct"], ha="right", fontsize=8, color=INK)
    a.set_xlabel("Assist level (% of the weak-to-strong torque gap)")
    a.set_ylabel("Peak battery current (A)")
    a.set_title("Assist sweep through the protection layer")
    a.legend(frameon=False, loc="upper left")

    a = ax[0, 1]
    rows = bus_study["rows"]
    xs = np.arange(len(rows))
    a.bar(xs - 0.2, [r["matlab_peak_A_at_48V"] for r in rows], width=0.4, color=GREY,
          label="Fixed 48 V")
    a.bar(xs + 0.2, [r["coupled_peak_A"] for r in rows], width=0.4, color=ORANGE,
          label="Live pack voltage")
    a.set_xticks(xs)
    a.set_xticklabels(["%d%%" % r["soc_pct"] for r in rows])
    a.set_xlabel("State of charge")
    a.set_ylabel("Peak battery current (A)")
    a.set_title("Effect of the fixed-voltage assumption")
    a.legend(frameon=False, loc="upper left")

    a = ax[1, 0]
    cycles_per_min = budget["cycles_per_minute"]
    labels = ["Produced by\nthe actuators", "Left after the\n%g W aux load" % budget["aux_load_W"]]
    vals = [budget["braking_energy_per_cycle_Wh_at_drivetrain"] * cycles_per_min,
            budget["braking_energy_per_cycle_Wh_reaching_the_pack"] * cycles_per_min]
    colors = [GREY, ORANGE]
    for name in ("S11", "S14"):
        r = by_name.get(name)
        if not r or "regen" not in r:
            continue
        led = r["regen"]
        dur = max(r["duration_simulated_s"], 1e-9)
        labels.append("Accepted, %s\n(%s)" % (name, r["description"].split(",")[-1].strip()[:18]))
        vals.append(led["energy_into_pack_Wh"] * 60.0 / dur)
        colors.append(GREEN)
    xs = np.arange(len(labels))
    a.bar(xs, vals, width=0.6, color=colors)
    for x, v in zip(xs, vals):
        a.text(x, v, " %.3f" % v, ha="center", va="bottom", fontsize=8, color=INK)
    a.set_xticks(xs)
    a.set_xticklabels(labels, fontsize=8)
    a.set_ylabel("Braking energy (Wh per minute of walking)")
    a.set_ylim(0, max(max(vals) * 1.25, 1e-3))
    a.set_title("Regeneration budget (PD-14 input)")

    a = ax[1, 1]
    tr = traces["S7"]
    a.plot(tr["t"], tr["i"], color=ORANGE, lw=1.2, label="Pack current (A)")
    a2 = a.twinx()
    a2.plot(tr["t"], tr["scale"], color=BLUE, lw=1.6, label="Commanded torque scale")
    a2.set_ylim(-0.05, 1.1)
    a2.set_ylabel("Torque scale")
    a2.grid(False)
    a.axvspan(8.0, 10.0, color=GREY, alpha=0.18)
    a.text(9.0, a.get_ylim()[1] * 0.92, "telemetry lost", ha="center", fontsize=8, color=INK)
    a.set_xlabel("Time (s)")
    a.set_ylabel("Pack current (A)")
    a.set_title("S7 closed loop: stale telemetry derates the assist torque")

    fig.suptitle("ELEC-SIM-001 v1.5 integration results: Electrical gait control model coupled "
                 "to the pack, the BMS and the regeneration path.", fontsize=10, color=INK)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(os.path.join(outdir, "ELEC-SIM-001_Integration_v1.5.png"), dpi=140)
    plt.close(fig)


def _regen_note(r):
    led = r.get("regen")
    if not led:
        return ""
    if not led["braking_energy_demanded_Wh"]:
        return "no charge reached the pack (auxiliary load absorbed the braking power)"
    frac = led["acceptance_fraction"]
    return "regen accepted %.1f%% of %.4f Wh, %s" % (
        100 * (frac or 0.0), led["braking_energy_demanded_Wh"],
        "limit " + max(led["binding_limit_sample_counts"],
                       key=led["binding_limit_sample_counts"].get)
        if any(led["binding_limit_sample_counts"].values()) else "no limit binding")


def _soc_of(result):
    """Starting SOC recovered from a scenario description for the figure label."""
    for token in result["description"].split():
        if token.endswith("%") and token[:-1].isdigit():
            return int(token[:-1])
    return result["end_soc_pct"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="results")
    ap.add_argument("--data", help="Comparison_Data XML from Electrical > Test Data")
    ap.add_argument("--assist", type=float, default=None)
    ap.add_argument("--soc", type=float, default=0.9)
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    outdir = args.outdir if os.path.isabs(args.outdir) else os.path.join(here, args.outdir)
    os.makedirs(outdir, exist_ok=True)

    data, is_real = gaitctl.load_gait_data(args.data)
    model = gaitctl.ExoAssistModel(data, assist=args.assist)
    if not is_real:
        print("WARNING: no Comparison_Data XML found in data/. Running on the synthetic "
              "stand-in. No number from this run may be reported.", file=sys.stderr)

    results, traces = scenarios.run_all(model)
    sweep = scenarios.assist_ceiling_study(model, soc0=args.soc)
    bus_study = scenarios.bus_voltage_study(model)
    envelope = regen_mod.acceptance_envelope()

    payload = {
        "simulation": "ELEC-SIM-001",
        "version": VERSION,
        "workstream": "Kiboard Warriors (ELEC-013, ELEC-014, ELEC-015)",
        "gait_control_model": {
            "ported_from": P["ctl_model_source"],
            "data_file": data.name,
            "data_is_authoritative": is_real,
            "metadata": getattr(data, "metadata", {}),
            "cycle_summary_at_configured_assist": model.summary(),
            "braking_budget_at_configured_assist": model.braking_budget(),
        },
        "params": table_for_json(),
        "parameters_not_cleared_for_design_use": unverified_keys(),
        "derived": derived_quantities(model, is_real),
        "results": results,
        "assist_ceiling_study": sweep,
        "bus_voltage_study": bus_study,
        "regen_acceptance_envelope": envelope,
    }
    json_path = os.path.join(outdir, "ELEC-SIM-001_Results_v1.5.json")
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    if not args.no_figures:
        make_figures(outdir, model, results, traces, sweep, bus_study, envelope,
                     payload["gait_control_model"]["braking_budget_at_configured_assist"])

    # ------------------------------------------------------------- console
    print("ELEC-SIM-001 v%s" % VERSION)
    print("gait data: %s (%s)" % (data.name, "authoritative" if is_real else "SYNTHETIC, not reportable"))
    s = model.summary()
    print("weak side %s, strong leg shifted %.1f%% of the cycle, cycle %.3f s"
          % (s["weak_side"], s["strong_leg_shift_pct"], s["cycle_s"]))
    print("MATLAB figures at 48 V: peak %.2f A, mean %.2f A, RMS %.2f A"
          % (s["matlab_peak_battery_A_at_48V"], s["matlab_mean_battery_A_at_48V"],
             s["matlab_rms_battery_A_at_48V"]))
    print()
    for r in results:
        print("%-4s %-9s %-24s peak %7.2f A  minV %6.2f  %s"
              % (r["scenario"], "TRIPPED" if r["tripped"] else "no trip", r["fault"],
                 r["peak_current_A"], r["min_pack_V"],
                 _regen_note(r)))
    print()
    print("highest assist without a trip: %s%%  (first trip at %s%%, %s)"
          % (sweep["highest_assist_without_trip_pct"], sweep["first_tripping_assist_pct"],
             sweep["first_trip_fault"]))
    print("results written to %s" % json_path)


if __name__ == "__main__":
    main()
