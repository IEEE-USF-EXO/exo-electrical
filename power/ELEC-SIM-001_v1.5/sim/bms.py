"""BMS protection state machine.

v1.5 change from v0.1: the charge and the discharge MOSFET paths are separate
states, as on the JK-B1A24S15P candidate. This matters for regeneration. A
cell overvoltage, a charge overcurrent or a charge temperature violation opens
the charge path and leaves the discharge path closed, so the exoskeleton keeps
walking while the pack stops accepting regenerated energy. An undervoltage, a
discharge overcurrent or a short circuit opens the discharge path. An
over-temperature opens both.

The state machine is hardware protection. It takes no input from firmware and
nothing in this module may be made dependent on the telemetry consumer
(ELEC-DOC-007 M-08).
"""
from .params import P

# fault -> (opens discharge path, opens charge path)
FAULT_PATHS = {
    "SHORT_CIRCUIT": (True, True),
    "DISCHARGE_OVERCURRENT": (True, False),
    "CELL_UNDERVOLTAGE": (True, False),
    "UNDER_TEMPERATURE": (True, False),
    "CHARGE_OVERCURRENT": (False, True),
    "CELL_OVERVOLTAGE": (False, True),
    "CHARGE_TEMP_INHIBIT": (False, True),
    "OVER_TEMPERATURE": (True, True),
}


class BMS:
    def __init__(self):
        self.dsg_closed = True
        self.chg_closed = True
        self.faults = []          # ordered list of (t, fault) latched events
        self.fault = ""           # most recent fault
        self.t_trip = None        # time of the first trip of any path
        self.timers = {k: 0.0 for k in ("ocd", "sc", "occ", "ov", "uv")}
        self.warnings = set()

    # ------------------------------------------------------------- reporting
    @property
    def closed(self):
        """True while both paths are closed (the v0.1 single-FET view)."""
        return self.dsg_closed and self.chg_closed

    @property
    def fault_code(self):
        return self.fault or "NONE"

    def state(self):
        return {"dsg_fet": "CLOSED" if self.dsg_closed else "OPEN",
                "chg_fet": "CLOSED" if self.chg_closed else "OPEN",
                "fault": self.fault_code}

    # ------------------------------------------------------------ protection
    def update(self, t, i_a, vc, temp_c, dt):
        """One protection step. i_a is the pack current actually flowing."""
        self.warnings.clear()

        # Hardware current protection, independent of firmware.
        self.timers["sc"] = self.timers["sc"] + dt if i_a > P["sc_trip_A"] else 0.0
        self.timers["ocd"] = self.timers["ocd"] + dt if i_a > P["ocp_dischg_A"] else 0.0
        self.timers["occ"] = self.timers["occ"] + dt if -i_a > P["ocp_chg_A"] else 0.0
        if self.timers["sc"] >= P["sc_delay_s"]:
            self._trip(t, "SHORT_CIRCUIT")
        if self.timers["ocd"] >= P["ocp_dischg_delay_s"]:
            self._trip(t, "DISCHARGE_OVERCURRENT")
        if self.timers["occ"] >= P["ocp_chg_delay_s"]:
            self._trip(t, "CHARGE_OVERCURRENT")

        # Cell voltage protection.
        self.timers["ov"] = self.timers["ov"] + dt if vc.max() >= P["ovp_trip_V"] else 0.0
        self.timers["uv"] = self.timers["uv"] + dt if vc.min() <= P["uvp_trip_V"] else 0.0
        if self.timers["ov"] >= P["ovp_delay_s"]:
            self._trip(t, "CELL_OVERVOLTAGE")
        if self.timers["uv"] >= P["uvp_delay_s"]:
            self._trip(t, "CELL_UNDERVOLTAGE")

        # Temperature protection. The allowed window depends on direction.
        lo, hi = P["charge_temp_C"] if i_a < 0 else P["discharge_temp_C"]
        if temp_c >= P["otp_trip_C"]:
            self._trip(t, "OVER_TEMPERATURE")
        elif temp_c < lo:
            self._trip(t, "CHARGE_TEMP_INHIBIT" if i_a < 0 else "UNDER_TEMPERATURE")
        elif temp_c > hi:
            self._trip(t, "OVER_TEMPERATURE")

        # Warnings are telemetry only. They open no path.
        if vc.max() >= P["ovp_warn_V"]:
            self.warnings.add("OVP_WARN")
        if vc.min() <= P["uvp_warn_V"]:
            self.warnings.add("UVP_WARN")
        if temp_c >= P["otp_warn_C"]:
            self.warnings.add("OTP_WARN")

    def _trip(self, t, why):
        opens_dsg, opens_chg = FAULT_PATHS[why]
        new = (opens_dsg and self.dsg_closed) or (opens_chg and self.chg_closed)
        if not new:
            return
        if opens_dsg:
            self.dsg_closed = False
        if opens_chg:
            self.chg_closed = False
        self.fault = why
        self.faults.append((round(t, 4), why))
        if self.t_trip is None:
            self.t_trip = t

    # --------------------------------------------------------------- gating
    def gate(self, i_cmd):
        """Current that the BMS lets through for a commanded pack current."""
        if i_cmd > 0.0:
            return i_cmd if self.dsg_closed else 0.0
        if i_cmd < 0.0:
            return i_cmd if self.chg_closed else 0.0
        return 0.0
