"""Scenario runner: the loop that ties the five layers together.

One time step, in order:

    gait control model   commanded assist torque, scaled by the controller
         |               derate factor from the previous step
         v
    DC-bus power  ->  solved against the live pack terminal voltage
         |
         + surge module (inrush, dual-actuator peak, bolted fault)
         v
    regen module   charge demand split into accepted and rejected
         |
         v
    BMS            protection state machine, charge and discharge paths
         |
         v
    pack           SOC, polarisation, temperature advance
         |
         v
    telemetry      10 Hz sample, staleness check, derate decision ------+
         |                                                              |
         +--> next step's torque scale -------------------------------->+

The derate feedback is the part v0.1 did not have. A BMS warning now reduces
the commanded assist torque, which reduces pack current, which can clear the
warning. Whether that loop settles or oscillates is a result of the run, not
an assumption in it.
"""
import numpy as np

from .bms import BMS
from .pack import Pack
from .params import P
from .regen import RegenLimiter
from .telemetry import TeensyConsumer

DT = P["dt_s"]


class Scenario:
    def __init__(self, name, description, duration, source=None, current_fn=None,
                 soc0=1.0, offsets=None, temp_fn=None, temp0=None, comm_drop=None,
                 surge_fn=None, regen_enabled=False, clamp_present=None,
                 closed_loop=True, balance_enable=True, assist=None,
                 scale_fault_current=False, stop_after_trip_s=0.5, run_to_end=False):
        self.name = name
        self.description = description
        self.duration = float(duration)
        self.source = source                # gait control model, or None
        self.current_fn = current_fn        # direct pack current demand [A]
        self.soc0 = soc0
        self.offsets = offsets
        self.temp_fn = temp_fn
        self.temp0 = temp0
        self.comm_drop = comm_drop
        self.surge_fn = surge_fn
        self.regen_enabled = regen_enabled
        self.clamp_present = clamp_present
        self.closed_loop = closed_loop
        self.balance_enable = balance_enable
        self.assist = assist
        self.scale_fault_current = scale_fault_current
        self.stop_after_trip_s = stop_after_trip_s
        self.run_to_end = run_to_end


def run(sc):
    pack = Pack(sc.soc0, sc.offsets, temp0=sc.temp0)
    bms = BMS()
    mcu = TeensyConsumer()
    regen = RegenLimiter(enabled=sc.regen_enabled, clamp_present=sc.clamp_present)

    n = int(round(sc.duration / DT))
    keys = ("t", "i", "i_cmd", "vpack", "vmax", "vmin", "temp", "soc",
            "scale", "p_bus", "mode", "dsg", "chg")
    log = {k: [] for k in keys}
    mode_time = {}
    next_tx = 0.0
    scale = 1.0
    energy_Wh = 0.0
    e_regen_into_pack_Wh = 0.0
    infeasible_steps = 0
    t_end = sc.duration

    for k in range(n):
        t = k * DT
        temp = sc.temp_fn(t) if sc.temp_fn else None
        eff_scale = scale if sc.closed_loop else 1.0

        # ------------------------------------------------ commanded current
        p_bus = float("nan")
        if sc.source is not None:
            p_bus = sc.source.at(t, torque_scale=eff_scale,
                                 regen_enabled=sc.regen_enabled,
                                 assist=sc.assist)["p_dc_W"]
            i_cmd, feasible = pack.current_for_power(p_bus)
            if not feasible:
                infeasible_steps += 1
        else:
            i_cmd = sc.current_fn(t)
            if sc.scale_fault_current:
                i_cmd *= eff_scale

        if sc.surge_fn is not None:
            i_cmd += sc.surge_fn(t)

        # ------------------------------------------------- regen limiting
        if i_cmd < 0.0:
            i_cmd, _ = regen.apply(i_cmd, pack, bms.chg_closed, DT, pack.source_v())

        # ----------------------------------------------------- protection
        i_a = bms.gate(i_cmd)
        vc = pack.cell_v(i_a)
        t_pack = pack.temp_C if temp is None else temp
        bms.update(t, i_a, vc, t_pack, DT)
        if bms.gate(i_cmd) != i_a:      # a trip this step opens the path now
            i_a = bms.gate(i_cmd)
            vc = pack.cell_v(i_a)

        bal = pack.balance_pair() if (sc.balance_enable and bms.closed) else None
        pack.step(i_a, bal, DT, temp_override=temp)

        v_pack = float(vc.sum()) - i_a * pack.extra_r
        energy_Wh += max(i_a, 0.0) * v_pack * DT / 3600.0
        if i_a < 0.0:
            e_regen_into_pack_Wh += -i_a * v_pack * DT / 3600.0

        # ------------------------------------------------------ telemetry
        if t >= next_tx:
            next_tx += P["telemetry_period_s"]
            if not (sc.comm_drop and sc.comm_drop[0] <= t < sc.comm_drop[1]):
                mcu.rx(t)
        scale = mcu.update(t, bms.warnings, bms.dsg_closed, DT)
        mode_time[mcu.mode] = mode_time.get(mcu.mode, 0.0) + DT

        # ----------------------------------------------------------- log
        if k % P["log_decimation"] == 0:
            log["t"].append(t)
            log["i"].append(i_a)
            log["i_cmd"].append(i_cmd)
            log["vpack"].append(v_pack)
            log["vmax"].append(float(vc.max()))
            log["vmin"].append(float(vc.min()))
            log["temp"].append(pack.temp_C if temp is None else temp)
            log["soc"].append(float(pack.soc.mean()))
            log["scale"].append(scale)
            log["p_bus"].append(p_bus)
            log["mode"].append(mcu.mode)
            log["dsg"].append(bms.dsg_closed)
            log["chg"].append(bms.chg_closed)

        if (not sc.run_to_end) and bms.t_trip is not None \
                and not bms.dsg_closed and (t - bms.t_trip) > sc.stop_after_trip_s:
            t_end = t
            break

    arr = {k: (np.array(v) if k != "mode" else v) for k, v in log.items()}
    res = {
        "scenario": sc.name,
        "description": sc.description,
        "duration_simulated_s": round(t_end, 3),
        "tripped": bms.t_trip is not None,
        "fault": bms.fault_code,
        "fault_sequence": bms.faults,
        "t_trip_s": None if bms.t_trip is None else round(bms.t_trip, 3),
        "fet_state": bms.state(),
        "peak_current_A": round(float(np.max(arr["i"])), 2),
        "min_current_A": round(float(np.min(arr["i"])), 2),
        "peak_demanded_current_A": round(float(np.max(arr["i_cmd"])), 2),
        "min_pack_V": round(float(np.min(arr["vpack"])), 2),
        "max_cell_V": round(float(np.max(arr["vmax"])), 3),
        "min_cell_V": round(float(np.min(arr["vmin"])), 3),
        "max_temp_C": round(float(np.max(arr["temp"])), 2),
        "end_soc_pct": round(100.0 * float(arr["soc"][-1]), 2),
        "discharge_energy_Wh": round(energy_Wh, 4),
        "regen_energy_into_pack_Wh": round(e_regen_into_pack_Wh, 5),
        "controller_events": mcu.events,
        "controller_mode_time_s": {k: round(v, 3) for k, v in mode_time.items()},
        "min_torque_scale": round(float(np.min(arr["scale"])), 3),
        "telemetry_stale_time_s": round(mcu.stale_time_s, 3),
        "closed_loop": sc.closed_loop,
        "power_solve_infeasible_steps": infeasible_steps,
    }
    if sc.source is not None:
        res["peak_bus_power_W"] = round(float(np.nanmax(arr["p_bus"])), 1)
        res["mean_bus_power_W"] = round(float(np.nanmean(arr["p_bus"])), 1)
    if sc.regen_enabled or regen.demand_Wh > 0:
        res["regen"] = regen.ledger(t_end)
    return res, arr
