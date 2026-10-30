# ELEC-SIM-001 v1.5 results

| Field | Value |
| --- | --- |
| Run date | 2026-10-22 |
| Gait input | `PostStroke_Moco_Comparison_Data_Hemi.xml` (Electrical > Test Data), 201 samples, last sample dropped as a repeat, 200 used |
| `gait_data_is_authoritative` | true |
| Assist level | 1.0 (weak leg fully matches the strong leg), `tauMax` 20 Nm, `hotFactor` 1.3, velocity from the weak leg |
| Weak side | Left, strong leg shifted 51.5% of the cycle |
| Gait cycle | 0.836 s, 71.8 cycles per minute |
| Auxiliary load | 45 W (Jetson 40 W, Teensy and sensors 5 W) |
| OCV | pchip, matching `battery_ocv.m` |
| Parameters not cleared for design use | 50 |

Full machine output: `ELEC-SIM-001_Results_v1.5.json` and the two figures, in
the package working copy. Every number below is read from that JSON.

**Status: preliminary.** No parameter has been measured on EXO hardware and no
BMS unit has been received (OI-09, PD-13). Nothing here selects a part,
justifies a purchase or supports a safety argument.

---

## 1. Port verification

The port of `one_sided_battery_current.m` was checked against an independent
re-implementation written from the MATLAB source, sharing no code with the
port. At assist 1.0:

| Figure | Port | Independent check |
| --- | --- | --- |
| Peak battery current at 48 V | 10.33 A | 10.33 A |
| Mean battery current at 48 V | 2.88 A | 2.88 A |
| RMS battery current at 48 V | 3.68 A | 3.68 A |
| Knee RMS phase current | 19.14 A | 19.14 A |
| Weak side, stride shift | Left, 51.5% | Left, 51.5% |

Maximum absolute difference 0.0041 A, which is rounding. The mean of 2.88 A
sits just under the 3 to 4 A quoted on the Electrical biweekly sheet of
2026-10-12, as expected at this assist setting.

This check catches a transcription error in the port. It does not catch a
misreading of the MATLAB semantics that both implementations share, so
**running `one_sided_battery_current.m` itself and comparing these three
numbers is still worth doing** and remains open.

---

## 2. The pack is not the limit. The knee actuator is.

The assist sweep from 0 to 100% was run through the pack and the BMS at 90%
SOC, four gait cycles per point.

| Assist | Peak pack current | Knee RMS phase current | Torque gap closed | Knee at torque limit | BMS |
| --- | --- | --- | --- | --- | --- |
| 25% | 2.76 A | 7.23 A | 25.0% | 0.0% | no trip |
| 40% | 4.53 A | 11.56 A | 40.0% | 0.0% | no trip |
| 45% | 5.33 A | 12.86 A | 44.5% | 6.5% | no trip |
| 50% | 5.90 A | 13.83 A | 48.9% | 12.5% | no trip |
| 75% | 10.51 A | 17.37 A | 57.6% | 30.5% | no trip |
| 100% | 11.71 A | 19.14 A | 59.3% | 48.0% | no trip |

**No assist level trips the pack.** Peak pack current at 100% assist is
11.7 A against a 45 A discharge overcurrent setting, a factor of nearly four
in hand.

The binding limit is thermal and it is in the actuator, not the battery. The
knee RMS phase current crosses the AK80-9 **12 A rated phase current between
40% and 45% assist**, and reaches 19.1 A at 100%. The knee is also at its
20 Nm torque clip for 48% of the gait cycle at full assist, so the extra
current buys little: going from 75% to 100% assist adds about 1.6 points of
gap closure and 1.8 A of knee RMS heating.

Two consequences for the control work:

1. An assist level above roughly 40% needs a thermal argument for the knee
   actuator, not a battery argument.
2. Returns flatten above 75% assist. If the knee thermal limit forces a
   choice, the cost of staying at 75% is small.

---

## 3. The fixed 48 V assumption understates battery current

The MATLAB model divides bus power by a constant 48 V. Against a real 12S1P
pack (50.4 V full, 43.2 V nominal, 0.20 ohm including busbar and FET):

| SOC | MATLAB at 48 V | Voltage effect only | Plus the 45 W aux load | Total error | Pack V at peak |
| --- | --- | --- | --- | --- | --- |
| 100% | 10.33 A | 10.25 A | 11.23 A | +8.8% | 48.1 V |
| 80% | 10.33 A | 10.98 A | 12.04 A | +16.6% | 44.9 V |
| 50% | 10.33 A | 11.67 A | 12.80 A | +23.9% | 42.3 V |
| 20% | 10.33 A | 12.75 A | 14.00 A | +35.6% | 38.6 V |
| 10% | 10.33 A | 14.12 A | 15.56 A | +50.7% | 34.7 V |

The two effects are separated because they have different owners. The voltage
effect is inherent to the pack and grows as it empties. The auxiliary load is
a modelling gap: the Jetson and Teensy draw from the same pack and are not in
the MATLAB model.

At 100% SOC the voltage effect is slightly negative, because a full pack sits
above 48 V.

**Use of this result:** a current figure quoted from the MATLAB model for
sizing should carry a factor for the state of charge it is meant to cover.
At the 20% SOC end of a mission the battery-side peak is about a third higher
than the 48 V figure.

---

## 4. Regeneration: there is almost nothing to recover (PD-14)

| Quantity | Value |
| --- | --- |
| Peak braking power at the drivetrain | 8.3 W |
| Braking energy per gait cycle at the drivetrain | 0.0001 Wh |
| Braking energy reaching the pack | 0.0 Wh |
| Rate at the drivetrain | 0.007 Wh per minute of walking |
| Auxiliary load | 45 W |

With the assist law as written, braking power never approaches the 45 W
auxiliary load, so **no charge current reaches the pack during gait at any
point in the cycle**. Scenarios S11, S12 and S14 confirm it at 98%, 98% with
the clamp fitted, and 40% SOC: the regeneration ledger records zero demand at
the pack in all three.

**Recommendation for PD-14:** the regeneration clamp cannot be justified by
gait assistance. The braking energy is three to four orders of magnitude
below what a clamp is for. If the clamp is to be kept on the BOM, the
justification has to come from a case this model does not cover, such as a
descent, a stair descent, sit-to-stand, or a driver fault that dumps the
motor-bus capacitance back into the pack. Electrical should state which of
those applies before the 90 USD is committed.

The pack-side acceptance limits are mapped anyway, because they govern
charging as well as regeneration:

| SOC | At 25 C | Binding limit | At minus 5 C |
| --- | --- | --- | --- |
| 50% | 13.50 A | charge overcurrent setting | 0.00 A |
| 90% | 8.67 A | cell overvoltage headroom | 0.00 A |
| 98% | 1.10 A | cell overvoltage headroom | 0.00 A |
| 100% | 0.00 A | cell overvoltage headroom | 0.00 A |

Below 0 C the pack accepts nothing at all, at any state of charge, because
the Molicel charge window starts at 0 C. Any charging arrangement needs a
temperature interlock, not only a voltage one.

---

## 5. Protection behaviour

| ID | Scenario | Result |
| --- | --- | --- |
| S1 | Nominal gait, 95% SOC, closed loop | No trip. Peak 11.61 A, minimum pack 46.59 V, mean bus power 182.7 W, 1.52 Wh over 30 s. Controller stays NORMAL throughout. |
| S2 | 56 A dual-actuator demand on top of gait | Discharge overcurrent at 2.001 s, exactly the 1.0 s delay after the demand starts. Peak 63.19 A. |
| S3 | Bolted fault, 150 A | Short circuit at 0.209 s, 9 ms after the fault, inside the 10 ms delay. Pack sags to 19.96 V during the fault. |
| S6 | Thermal ramp at 3.5 A | Over-temperature at 60.0 s on the 55 C trip, after the 50 C warning derates the controller. |
| S7 | 2 s telemetry dropout during gait | No trip. Stale detected at 8.401 s, 401 ms after the last good sample, consistent with the 500 ms staleness setting and the 10 Hz rate. Torque scale falls to 0.40 and recovers at 10.999 s, one second after data returns. |
| S10 | Dual-actuator peak once per stride, 0.4 s each | **No trip, peak 65.12 A.** |
| S13 | Gait at 12% SOC | No trip, but minimum pack voltage 36.23 V against a 36.0 V undervoltage trip. |

Two results deserve attention.

**S10, the repeated surge.** A 65 A demand lasting 0.4 s, once per stride,
never trips anything: it is below the 100 A short-circuit threshold and
shorter than the 1.0 s overcurrent delay. It is 14.5 C on the cell and 20 A
above the 45 A continuous rating, repeated 72 times a minute. The protection
settings as proposed do not catch this duty cycle, and nothing in the BMS
would. If a repeated peak demand of this shape is realistic, the cell duty
needs its own argument (RK-01), or the overcurrent delay needs shortening.
The stacked worst case is 66.3 A, 14.7 C, 21.3 A over the cell continuous
rating.

**S13, low state of charge.** At 12% SOC the controller sits in DERATE_WARN
for the whole 40 s run, because the lowest cell is under the 3.30 V warning
threshold from the start, and the pack bottoms out 0.23 V above the
undervoltage trip. The end of a mission is therefore a permanently derated
state followed by a trip with little warning. Either the undervoltage warning
threshold or the usable SOC window needs setting deliberately rather than
inherited from the datasheet.

---

## 6. Inrush: the BMS does not protect the contactor (RK-03)

Closing the motor bus onto an assumed 1000 uF of drive capacitance, pack at
full charge:

| Case | Peak inrush | Time to 95% | BMS trips |
| --- | --- | --- | --- |
| No precharge resistor | 250.8 A | 0.60 ms | No |
| 22 ohm precharge resistor | 2.3 A | 66.6 ms | No |

Without a precharge resistor the inrush is 250 A, two and a half times the
100 A short-circuit setting, but it lasts 0.6 ms against a 10 ms delay, so
**the BMS never sees it.** This is a contactor, connector and FET rating
question, and the protection layer gives no cover for it. The BOM lists
precharge as Not chosen (RK-03). The energy involved is 1.27 J per closure,
which any modest resistor handles.

The bus capacitance is ASSUMED: no capacitor appears on the BOM. Confirm the
drive input capacitance from the AK60 driver documentation before using the
250 A figure.

---

## 7. What to do next

1. Run `one_sided_battery_current.m` and compare the three battery-current
   figures in Section 1. The port agrees with an independent re-write, but
   not yet with MATLAB itself.
2. Take the knee thermal limit (Section 2) to Controls. The assist ceiling is
   an actuator decision, not a battery one.
3. Close PD-14 using Section 4. The gait case does not justify the clamp.
4. Decide whether the S10 duty cycle is realistic, and if so revisit the
   overcurrent delay (Section 5, RK-01).
5. Fit a precharge resistor or rate the contactor for 250 A (Section 6).
6. Review the derate ladder with Controls as the I-08 draft. Every value in
   it is PROPOSED.
