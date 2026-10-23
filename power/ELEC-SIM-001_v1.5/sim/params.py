"""Parameter registry.

Every entry is (value, unit, source tag). An entry whose tag names a
manufacturer document or a measurement is usable for a design decision. A tag
of PROPOSED, ASSUMED or OPEN is not: it shall be replaced or confirmed first.
The runner writes this whole table into the results JSON, so no number leaves
the model without its source.

v1.5 adds the regen, surge, gait-coupling and controller-derate groups, and
replaces the v0.1 linear OCV placeholder with the pchip shape used by the
Electrical AK80 battery/gait MATLAB model so both models share one OCV.
"""

PARAMS = {
    # ------------------------------------------------------------------ pack
    "n_series": (12, "cells", "BOM, Molicel P45B 12S1P pack; Master Log D-016"),
    "n_parallel": (1, "cells", "BOM 12S1P"),
    "cell_capacity_Ah": (4.5, "Ah", "BOM note; Molicel typical (minimum 4.3)"),
    "cell_dcir_ohm": (0.015, "ohm", "Molicel datasheet typical DC, 50% SOC (secondary retailer copy)"),
    "cell_v_max": (4.20, "V", "Molicel datasheet charge voltage"),
    "cell_v_nom": (3.60, "V", "Molicel datasheet nominal"),
    "cell_v_cutoff": (2.50, "V", "Molicel datasheet end of discharge"),
    "cell_i_cont_A": (45.0, "A", "BOM note; Molicel datasheet (80 C cell cutoff)"),
    "cell_i_chg_max_A": (13.5, "A", "Molicel datasheet maximum charge (70 C cutoff)"),
    "charge_temp_C": ((0.0, 60.0), "C", "Molicel datasheet"),
    "discharge_temp_C": ((-40.0, 60.0), "C", "Molicel datasheet (one retailer lists 80 C upper)"),
    "balance_current_A": (1.0, "A", "BOM note, 1 A active balance"),
    "ocv_model": ("pchip NMC/NCA normalised shape, 2.50 V to 4.20 V", "",
                  "battery_ocv.m (Electrical AK80 model v2.2); ASSUMED sizing curve, not a measured OCV"),
    "dcir_spread": (0.10, "fraction", "ASSUMED cell-to-cell DCIR spread, uniform +/-10%"),
    "dcir_lowsoc_mult": (1.25, "x", "exo_model_config.m battery.low_soc_resistance_multiplier (ASSUMED)"),
    "dcir_lowsoc_knee": (0.15, "SOC", "exo_model_config.m battery.low_soc_check (ASSUMED)"),
    "dcir_temp_coeff_per_C": (-0.010, "1/C", "ASSUMED, 1% DCIR rise per degree below 25 C, clamped to 0.6x..2.5x"),
    "pack_extra_r_ohm": (0.020, "ohm",
                         "exo_model_config.m battery.pack_extra_resistance_Ohm: busbar, BMS FET, harness (ASSUMED)"),
    "cell_rp_ohm": (0.008, "ohm", "ASSUMED placeholder, same role as Rp_Ohm in battery_gait_ode_rhs.m"),
    "cell_cp_F": (900.0, "F", "ASSUMED placeholder, same role as Cp_F in battery_gait_ode_rhs.m"),
    "pack_cth_J_per_K": (1040.0, "J/K",
                         "ASSUMED, 12 x 0.069 kg x 1255 J/kgK (Li-ion cell specific heat, literature class value)"),
    "pack_rth_K_per_W": (2.2, "K/W", "ASSUMED still-air belt enclosure; no thermal test on record"),
    "ambient_temp_C": (25.0, "C", "ASSUMED laboratory ambient"),

    # ------------------------------------------------------ BMS trip settings
    # All PROPOSED for team review, derived from the datasheet limits above.
    "ovp_trip_V": (4.20, "V/cell", "PROPOSED = cell maximum"),
    "ovp_warn_V": (4.18, "V/cell", "PROPOSED"),
    "ovp_delay_s": (0.100, "s", "PROPOSED"),
    "uvp_trip_V": (3.00, "V/cell", "PROPOSED, margin above the 2.5 V cutoff"),
    "uvp_warn_V": (3.30, "V/cell", "PROPOSED"),
    "uvp_delay_s": (0.500, "s", "PROPOSED, so load sag does not trip UVP before the short-circuit path"),
    "ocp_dischg_A": (45.0, "A", "PROPOSED = cell continuous rating"),
    "ocp_dischg_delay_s": (1.0, "s", "PROPOSED"),
    "sc_trip_A": (100.0, "A", "PROPOSED, below the 150 A BMS continuous rating"),
    "sc_delay_s": (0.010, "s", "PROPOSED"),
    "ocp_chg_A": (13.5, "A", "PROPOSED = cell maximum charge"),
    "ocp_chg_delay_s": (1.0, "s", "PROPOSED"),
    "otp_warn_C": (50.0, "C", "PROPOSED"),
    "otp_trip_C": (55.0, "C", "PROPOSED, 5 C below the 60 C datasheet limit"),
    "balance_start_V": (4.00, "V/cell", "PROPOSED"),
    "balance_delta_V": (0.030, "V", "PROPOSED"),

    # ------------------------------------------------- telemetry and derate
    "telemetry_period_s": (0.100, "s", "PROPOSED 10 Hz, ELEC-DOC-007 M-05"),
    "telemetry_stale_s": (0.500, "s", "PROPOSED, ELEC-DOC-007 M-06"),
    "derate_warn_frac": (0.60, "fraction of commanded torque",
                         "PROPOSED, no Controls agreement on record (I-08)"),
    "derate_stale_frac": (0.40, "fraction of commanded torque", "PROPOSED, ELEC-DOC-007 M-06"),
    "derate_stop_frac": (0.0, "fraction of commanded torque",
                         "PROPOSED, CTRL-005 software stop commands zero torque"),
    "derate_tau_s": (0.150, "s", "PROPOSED first-order torque ramp, avoids a step change in assistance"),
    "derate_recover_s": (1.00, "s", "PROPOSED hold time of fresh data before leaving a derate state"),

    # ----------------------------------------------------------------- regen
    "regen_enabled_default": (False, "bool",
                              "exo_model_config.m assist.regen_enabled = false, no regen credit until bench data exist"),
    "regen_v_headroom_V": (0.020, "V/cell",
                           "PROPOSED, hold the highest cell this far below the OVP trip while charging"),
    "regen_temp_lo_C": (0.0, "C", "Molicel charge temperature minimum, charge inhibited below this"),
    "regen_temp_taper_lo_C": (5.0, "C", "PROPOSED taper band, 0 A at 0 C rising to full acceptance at 5 C"),
    "regen_temp_taper_hi_C": (45.0, "C", "PROPOSED, taper to zero between here and the 55 C OTP trip"),
    "regen_soc_full": (0.995, "SOC", "PROPOSED, accept no charge above this SOC"),
    "clamp_present": (False, "bool",
                      "PD-14 OPEN, regeneration clamp (90 USD, 12 to 58 V, 80 A continuous) neither selected nor rejected"),
    "clamp_threshold_V": (51.0, "V pack",
                          "PROPOSED turn-on, above the 50.4 V full-charge pack and below the 52 V driver maximum"),
    "clamp_r_ohm": (2.0, "ohm", "ASSUMED dissipation resistor, no part selected (PD-14)"),

    # ----------------------------------------------------------------- surge
    "bus_capacitance_uF": (1000.0, "uF", "ASSUMED motor-bus bulk capacitance, no capacitor on the BOM"),
    "precharge_r_ohm": (22.0, "ohm",
                        "PROPOSED precharge resistor, not on the BOM (RK-03 lists precharge as Not chosen)"),
    "actuator_peak_A_each": (28.0, "A", "Technical Baseline 6.1, AK80-9 peak phase current"),
    "actuator_count": (2, "actuators", "Technical Baseline, powered hip and knee, Phase 1 unilateral"),
    "surge_dual_peak_A": (56.0, "A",
                          "BOM worst case 2 x 28 A, exceeds the 45 A cell rating by 11 A (RK-01)"),
    "surge_rise_s": (0.002, "s", "ASSUMED current-loop rise time of the AK60 driver"),

    # ------------- primary gait control model (Electrical > Test Data, Luis)
    # Ported from one_sided_battery_current.m and battery_current.m. These are
    # the Electrical team's own drivetrain numbers and shall not be changed
    # here: change them in the MATLAB source and re-port.
    "ctl_model_source": ("one_sided_battery_current.m (Electrical > Test Data, Drive)", "",
                         "Drive file 1GuL6SPkEZCvy-13y5pJZoSzvVO283Mw2, modified 2026-09-30"),
    "ctl_data_hemi": ("PostStroke_Moco_Comparison_Data_Hemi.xml, 201 samples", "",
                      "Electrical > Test Data; OpenSim Moco post-stroke gait prediction, model 40p 11d24m"),
    "ctl_data_healthy": ("Healthy_Gait_Comparison_Data.xml, 135 samples", "",
                         "Electrical > Test Data; OpenSim inverse dynamics, 6 Hz kinematic low pass"),
    "ctl_assist": (1.0, "fraction of the weak-to-strong torque gap",
                   "one_sided_battery_current.m assist (1 = weak leg fully matches the strong leg)"),
    "ctl_weak_side": ("auto", "", "one_sided_battery_current.m weakSide, auto picks the lower RMS-moment side"),
    "ctl_velocity_from": ("weak", "", "one_sided_battery_current.m velocityFrom"),
    "ctl_tau_max_Nm": (20.0, "Nm", "one_sided_battery_current.m tauMax (AK80-9 peak is 22 Nm)"),
    "ctl_hot_factor": (1.3, "-", "one_sided_battery_current.m hotFactor, hot-winding copper-loss multiplier"),
    "ctl_gear_ratio": (9.0, "-", "one_sided_battery_current.m N; AK80-9 datasheet"),
    "ctl_gear_eff": (0.90, "-", "one_sided_battery_current.m eg"),
    "ctl_ctrl_eff": (0.95, "-", "one_sided_battery_current.m ec"),
    "ctl_kt_Nm_per_A": (0.095, "Nm/A", "one_sided_battery_current.m Kt, motor side"),
    "ctl_km_Nm_per_sqrtW": (0.2387, "Nm/sqrt(W)", "one_sided_battery_current.m Km, motor constant"),
    "ctl_bus_V_fixed": (48.0, "V", "one_sided_battery_current.m V, the fixed bus voltage v1.5 replaces"),
    "ctl_include_aux_load": (True, "bool",
                             "v1.5 addition: the MATLAB model carries no auxiliary load; the pack does"),

    # ----------------------- secondary gait source (AK80 sizing model, cross-check)
    "gait_source": ("EXO_AK80_Battery_Gait_Model_v2_2, Fukuchi young overground template", "",
                    "healthy_gait_profile.m with data/fukuchi_young_overground_engineering_template.csv"),
    "gait_mode": ("comfortable", "", "user_inputs.m gait_mode"),
    "cadence_spm": (110.0, "steps/min", "user_inputs.m steps_per_min"),
    "subject_mass_kg": (77.1107, "kg", "user_inputs.m subject_mass_kg (170 lb)"),
    "hip_assist_frac": (0.20, "fraction of healthy hip moment", "user_inputs.m hip_assist_pct"),
    "knee_assist_frac": (0.20, "fraction of healthy knee moment", "user_inputs.m knee_assist_pct"),
    "actuator_peak_torque_Nm": (22.0, "Nm", "exo_model_config.m actuator.peak_torque_Nm (CubeMars AK80-9 V3.0)"),
    "actuator_kt_Nm_per_A": (0.095, "Nm/A", "exo_model_config.m actuator.motor_Kt_Nm_per_A"),
    "gear_ratio": (9.0, "-", "exo_model_config.m actuator.gear_ratio"),
    "gear_eff_motoring": (0.92, "-", "exo_model_config.m (ASSUMED loss model, no bench data)"),
    "gear_eff_regen": (0.85, "-", "exo_model_config.m (ASSUMED)"),
    "inverter_eff": (0.97, "-", "exo_model_config.m (ASSUMED)"),
    "regen_conversion_eff": (0.80, "-", "exo_model_config.m actuator.regen_conversion_eff (ASSUMED)"),
    "copper_r_ohm": (0.080, "ohm", "exo_model_config.m actuator.effective_copper_R_Ohm (ASSUMED)"),
    "driver_idle_W": (1.0, "W", "exo_model_config.m actuator.driver_idle_W (ASSUMED)"),
    "electronics_W": (45.0, "W", "user_inputs.m orin_nominal_W 40 plus controls_sensors_W 5"),
    "electronics_conservative_W": (65.0, "W", "user_inputs.m orin_conservative_W 60 plus 5"),

    # ---------------------------------------------------------------- solver
    "dt_s": (0.001, "s", "Chosen so the 10 ms short-circuit delay is resolved"),
    "log_decimation": (10, "steps", "Logging stride, 100 Hz logged output"),
}

P = {k: v[0] for k, v in PARAMS.items()}


def table_for_json():
    return {k: [str(v[0]), v[1], v[2]] for k, v in PARAMS.items()}


def unverified_keys():
    """Parameters that may not drive a design decision yet."""
    return sorted(k for k, v in PARAMS.items()
                  if any(tag in v[2] for tag in ("PROPOSED", "ASSUMED", "OPEN")))
