"""Controller-side telemetry consumer (Teensy 4.1).

The BMS is an independent protection layer. This consumer only derates, stops
torque and logs (ELEC-DOC-007 M-05 to M-08).

v1.5 change from v0.1: the consumer returns a torque scale factor that the
gait layer applies to the commanded joint torque, so a derate decision changes
pack current inside the same run instead of only appearing in an event list.
The ladder values, the ramp and the recovery hold are all PROPOSED and have no
Controls agreement on record (interface I-08).
"""
from .params import P

MODE_SCALE = {
    "NORMAL": 1.0,
    "DERATE_WARN": P["derate_warn_frac"],
    "DERATE_STALE": P["derate_stale_frac"],
    "STOP_TORQUE": P["derate_stop_frac"],
}


class TeensyConsumer:
    def __init__(self):
        self.last_rx = 0.0
        self.mode = "NORMAL"
        self.scale = 1.0
        self.events = []
        self._clear_since = 0.0
        self.rx_count = 0
        self.stale_time_s = 0.0

    def rx(self, t):
        self.last_rx = t
        self.rx_count += 1

    def update(self, t, warnings, dsg_closed, dt):
        """Advance the consumer. Returns the torque scale to command."""
        stale = (t - self.last_rx) > P["telemetry_stale_s"]
        if stale:
            self.stale_time_s += dt

        if not dsg_closed:
            want = "STOP_TORQUE"
        elif stale:
            want = "DERATE_STALE"
        elif warnings:
            want = "DERATE_WARN"
        else:
            want = "NORMAL"

        # Leaving a derate state requires the condition to stay clear for the
        # recovery hold. A stop latches: only a BMS reset clears it.
        if want == "NORMAL" and self.mode != "NORMAL":
            if self.mode == "STOP_TORQUE":
                want = "STOP_TORQUE"
            elif (t - self._clear_since) < P["derate_recover_s"]:
                want = self.mode
        else:
            self._clear_since = t

        if want != self.mode:
            self.events.append((round(t, 3), self.mode, want))
            self.mode = want

        target = MODE_SCALE[self.mode]
        tau = max(P["derate_tau_s"], 1e-9)
        self.scale += (target - self.scale) * min(dt / tau, 1.0)
        return self.scale
