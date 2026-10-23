"""12S1P pack model: OCV, state of charge, DC resistance, first-order
polarisation, and a lumped thermal state.

The OCV shape and the normalised knots are taken from battery_ocv.m in the
Electrical AK80 battery/gait MATLAB model so that the two models cannot
disagree about cell voltage at a given SOC. The shape is a sizing curve, not a
measured OCV (see params.ocv_model).

Sign convention, used identically here, in the MATLAB model and in the BMS:
    current I > 0 discharges the pack, I < 0 charges it
    power   P > 0 discharges the pack, P < 0 is net regeneration
"""
import numpy as np

from .params import P

# Normalised OCV knots for the NMC/NCA class cell (battery_ocv.m).
_SOC_KNOTS = np.array([0.0, 0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 0.95, 1.00])
_V_NORM = np.array([0.0, 0.28, 0.42, 0.56, 0.69, 0.76, 0.85, 0.95, 1.00])

try:  # pchip matches the MATLAB interp1(...,'pchip') call exactly
    from scipy.interpolate import PchipInterpolator

    _SHAPE = PchipInterpolator(_SOC_KNOTS, _V_NORM)
    OCV_INTERP = "pchip (scipy), matches battery_ocv.m"
except Exception:  # pragma: no cover - fallback keeps the model runnable
    def _SHAPE(x):
        return np.interp(x, _SOC_KNOTS, _V_NORM)

    OCV_INTERP = "linear on the battery_ocv.m knots (scipy unavailable); differs from MATLAB by <0.02 V"


def ocv(soc):
    """Open-circuit cell voltage [V] from state of charge [0-1]."""
    s = np.clip(soc, 0.0, 1.0)
    vmin, vmax = P["cell_v_cutoff"], P["cell_v_max"]
    return vmin + np.asarray(_SHAPE(s)) * (vmax - vmin)


class Pack:
    """12 series cells with individual SOC, DCIR and polarisation states."""

    def __init__(self, soc0=1.0, soc_offsets=None, seed=1, temp0=None):
        n = P["n_series"]
        rng = np.random.default_rng(seed)
        self.n = n
        self.soc = np.full(n, float(soc0))
        if soc_offsets:
            for i, d in soc_offsets.items():
                self.soc[i] = min(1.0, self.soc[i] + d)
        self.r0 = P["cell_dcir_ohm"] * (1 + P["dcir_spread"] * rng.uniform(-1, 1, n))
        self.vpol = np.zeros(n)
        self.q_As = P["cell_capacity_Ah"] * 3600.0
        self.temp_C = P["ambient_temp_C"] if temp0 is None else float(temp0)
        self.extra_r = P["pack_extra_r_ohm"]

    # ------------------------------------------------------------ resistance
    def cell_r(self):
        """Per-cell DC resistance at the present SOC and temperature."""
        mult = np.where(self.soc < P["dcir_lowsoc_knee"], P["dcir_lowsoc_mult"], 1.0)
        t_mult = 1.0 + P["dcir_temp_coeff_per_C"] * (self.temp_C - P["ambient_temp_C"])
        t_mult = float(np.clip(t_mult, 0.6, 2.5))
        return self.r0 * mult * t_mult

    def pack_r(self):
        """Total pack series resistance including busbar, FET and harness."""
        return float(self.cell_r().sum()) + self.extra_r

    # --------------------------------------------------------------- voltages
    def cell_ocv(self):
        return ocv(self.soc)

    def cell_v(self, i_a):
        """Terminal voltage of each cell at pack current i_a [A]."""
        return self.cell_ocv() - self.vpol - i_a * self.cell_r()

    def pack_v(self, i_a):
        """Pack terminal voltage [V] at the BMS output, extra_r included."""
        return float(self.cell_v(i_a).sum()) - i_a * self.extra_r

    def source_v(self):
        """Pack voltage behind the series resistance (OCV less polarisation)."""
        return float((self.cell_ocv() - self.vpol).sum())

    # ------------------------------------------------- power to current solve
    def current_for_power(self, p_w):
        """Solve P = (Vsrc - I*R)*I for the low-current root.

        Identical algebra to pack_current_from_power.m in the Electrical
        MATLAB model. Returns (I_A, feasible). Infeasible means the pack
        cannot deliver that power at any current: the discriminant is
        negative, which is a voltage-collapse condition, not a valid root.
        """
        vsrc, r = self.source_v(), self.pack_r()
        if r <= 0:
            return p_w / max(vsrc, 1e-9), True
        disc = vsrc ** 2 - 4.0 * r * p_w
        if disc < 0.0:
            return vsrc / (2.0 * r), False
        return (vsrc - np.sqrt(disc)) / (2.0 * r), True

    # ------------------------------------------------------------------ step
    def step(self, i_a, balancing, dt, temp_override=None):
        """Advance SOC, polarisation and temperature by dt [s]."""
        r_now = self.cell_r()
        self.soc = np.clip(self.soc - i_a * dt / self.q_As, 0.0, 1.0)

        rp, cp = P["cell_rp_ohm"], P["cell_cp_F"]
        self.vpol += dt * (-self.vpol / (rp * cp) + i_a / cp)

        if temp_override is None:
            heat = i_a ** 2 * (float(r_now.sum()) + self.extra_r) \
                + float(np.sum(self.vpol ** 2) / max(rp, 1e-12))
            cooling = (self.temp_C - P["ambient_temp_C"]) / P["pack_rth_K_per_W"]
            self.temp_C += dt * (heat - cooling) / P["pack_cth_J_per_K"]
        else:
            self.temp_C = float(temp_override)

        if balancing is not None:
            hi, lo = balancing
            dq = P["balance_current_A"] * dt / self.q_As
            self.soc[hi] = max(0.0, self.soc[hi] - dq)
            self.soc[lo] = min(1.0, self.soc[lo] + dq)

    # ------------------------------------------------------------- balancing
    def balance_pair(self):
        """Cells to move charge between, or None if no balancing is needed."""
        v_rest = self.cell_ocv()
        if v_rest.max() <= P["balance_start_V"]:
            return None
        if (v_rest.max() - v_rest.min()) <= P["balance_delta_V"]:
            return None
        return int(np.argmax(v_rest)), int(np.argmin(v_rest))
