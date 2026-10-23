"""Regeneration module.

The Electrical control model (one_sided_battery_current.m) sets battery power
to zero on every braking sample: Pb(Pe <= 0) = 0. That is the right
conservative choice for sizing, but it leaves two questions unanswered, and
both are open items on the program:

    PD-14  The regeneration clamp (90 USD, 12 to 58 V, 80 A continuous) is
           neither selected nor rejected. The decision was deferred until
           Electrical states the failure mode, the condition it applies to,
           and the regeneration energy.
    RK-10  The BOM review of 2026-10-17 flags the clamp as having no decision.

This module answers them quantitatively. For a given braking current demand it
computes what the pack will accept and what has to go somewhere else.

Charge acceptance is the lowest of four limits:
    1. Cell overvoltage headroom. The highest cell shall stay regen_v_headroom
       below the OVP trip, so the accepted current is bounded by that headroom
       divided by the cell resistance.
    2. The BMS charge overcurrent setting (13.5 A, the cell maximum charge).
    3. Temperature. Charge is inhibited below 0 C (datasheet), tapered from
       0 to 5 C, and tapered again above 45 C towards the 55 C OTP trip.
    4. State of charge. No acceptance above regen_soc_full.

Everything the pack will not take is reported as rejected power. With a clamp
fitted it is dissipated once the pack passes the clamp threshold. Without one
the motor controller has to limit braking torque, which is a requirement back
on the control model, not a free choice.
"""
import numpy as np

from .params import P


class RegenLimiter:
    def __init__(self, enabled=None, clamp_present=None):
        self.enabled = P["regen_enabled_default"] if enabled is None else bool(enabled)
        self.clamp_present = P["clamp_present"] if clamp_present is None else bool(clamp_present)
        self.reset()

    def reset(self):
        self.accepted_Wh = 0.0
        self.rejected_Wh = 0.0
        self.clamp_Wh = 0.0
        self.demand_Wh = 0.0
        self.peak_demand_A = 0.0
        self.peak_accepted_A = 0.0
        self.peak_clamp_W = 0.0
        self.clamp_on_time_s = 0.0
        self.limit_counts = {"ovp_headroom": 0, "charge_ocp": 0, "temperature": 0, "soc": 0}

    # ---------------------------------------------------------- acceptance
    def acceptance_A(self, pack, temp_c=None):
        """Charge current the pack may accept right now [A, magnitude]."""
        t = pack.temp_C if temp_c is None else float(temp_c)
        r = pack.cell_r()
        v_rest = pack.cell_ocv() - pack.vpol
        headroom = (P["ovp_trip_V"] - P["regen_v_headroom_V"]) - v_rest
        i_ovp = float(np.min(np.maximum(headroom, 0.0) / r))
        i_ocp = P["ocp_chg_A"]

        lo, taper_lo, taper_hi = (P["regen_temp_lo_C"], P["regen_temp_taper_lo_C"],
                                  P["regen_temp_taper_hi_C"])
        if t < lo:
            f_t = 0.0
        elif t < taper_lo:
            f_t = (t - lo) / max(taper_lo - lo, 1e-9)
        elif t <= taper_hi:
            f_t = 1.0
        else:
            f_t = max(0.0, 1.0 - (t - taper_hi) / max(P["otp_trip_C"] - taper_hi, 1e-9))
        i_temp = i_ocp * f_t

        i_soc = 0.0 if float(pack.soc.max()) >= P["regen_soc_full"] else i_ocp

        limits = {"ovp_headroom": i_ovp, "charge_ocp": i_ocp,
                  "temperature": i_temp, "soc": i_soc}
        name = min(limits, key=limits.get)
        return max(0.0, limits[name]), name, limits

    # --------------------------------------------------------------- apply
    def apply(self, i_cmd, pack, chg_path_closed, dt, v_pack):
        """Split a commanded pack current into accepted and rejected parts.

        i_cmd < 0 is a charge demand. Returns (i_pack, detail).
        """
        if i_cmd >= 0.0:
            return i_cmd, {"regen": False}

        demand = -i_cmd
        self.demand_Wh += demand * v_pack * dt / 3600.0
        self.peak_demand_A = max(self.peak_demand_A, demand)

        if not self.enabled or not chg_path_closed:
            accept = 0.0
            limit = "disabled" if not self.enabled else "charge_path_open"
        else:
            accept, limit, _ = self.acceptance_A(pack)
            accept = min(accept, demand)
            if accept < demand:
                self.limit_counts[limit] = self.limit_counts.get(limit, 0) + 1

        rejected_A = demand - accept
        rejected_W = rejected_A * v_pack
        self.accepted_Wh += accept * v_pack * dt / 3600.0
        self.rejected_Wh += rejected_W * dt / 3600.0
        self.peak_accepted_A = max(self.peak_accepted_A, accept)

        clamp_W = 0.0
        if self.clamp_present and rejected_W > 0.0 and v_pack >= P["clamp_threshold_V"]:
            clamp_W = min(rejected_W, v_pack ** 2 / P["clamp_r_ohm"])
            self.clamp_Wh += clamp_W * dt / 3600.0
            self.clamp_on_time_s += dt
            self.peak_clamp_W = max(self.peak_clamp_W, clamp_W)

        return -accept, {"regen": True, "demand_A": demand, "accepted_A": accept,
                         "rejected_A": rejected_A, "limit": limit, "clamp_W": clamp_W}

    # -------------------------------------------------------------- report
    def ledger(self, duration_s):
        unhandled = self.rejected_Wh - self.clamp_Wh
        return {
            "regen_enabled": self.enabled,
            "clamp_fitted": self.clamp_present,
            "braking_energy_demanded_Wh": round(self.demand_Wh, 5),
            "energy_into_pack_Wh": round(self.accepted_Wh, 5),
            "energy_rejected_Wh": round(self.rejected_Wh, 5),
            "energy_into_clamp_Wh": round(self.clamp_Wh, 5),
            "energy_the_drive_must_refuse_Wh": round(max(unhandled, 0.0), 5),
            "acceptance_fraction": round(self.accepted_Wh / self.demand_Wh, 4) if self.demand_Wh > 0 else None,
            "peak_demand_A": round(self.peak_demand_A, 2),
            "peak_accepted_A": round(self.peak_accepted_A, 2),
            "peak_clamp_power_W": round(self.peak_clamp_W, 1),
            "clamp_duty_fraction": round(self.clamp_on_time_s / duration_s, 4) if duration_s > 0 else 0.0,
            "binding_limit_sample_counts": dict(self.limit_counts),
        }


def acceptance_envelope(soc_values=(0.5, 0.8, 0.9, 0.95, 0.98, 1.0),
                        temp_values=(-5.0, 0.0, 10.0, 25.0, 45.0, 50.0)):
    """Charge acceptance over SOC and temperature, nominal cell, at rest.

    v0.1 produced the SOC column of this table only, at 25 C. The temperature
    axis is what rules out regeneration on a cold start: the Molicel charge
    window starts at 0 C, so a pack below freezing accepts nothing at all
    however much braking energy the gait produces.
    """
    from .pack import Pack

    rows = []
    for soc in soc_values:
        for t in temp_values:
            pack = Pack(soc0=soc, seed=0, temp0=t)
            pack.r0 = np.full(pack.n, P["cell_dcir_ohm"])  # nominal cell, no spread
            amps, limit, _ = RegenLimiter(enabled=True).acceptance_A(pack, temp_c=t)
            rows.append({"soc_pct": int(round(soc * 100)), "temp_C": t,
                         "ocv_V": round(float(pack.cell_ocv()[0]), 3),
                         "max_regen_A": round(amps, 2), "binding_limit": limit})
    return rows
