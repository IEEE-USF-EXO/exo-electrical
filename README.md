# exo-electrical

Electrical design for the EXO Phase 1 leg: power, sensors, harness, and CAN wiring. Electrical owns sensor hardware, wiring, and connectors (Baseline §3).

| Field | Value |
| --- | --- |
| Owner | Electrical lead |
| Program | IEEE EXO, Phase 1 (unilateral prototype) |
| Current version | v0.1 (scaffold) |

## Current work

Each package lists its sub-team, its deliverables, what shows the work is done, and the Drive folder for its files. Owner for every package: assigned by the Electrical lead. Dates are planned targets.

Recorded hardware facts: the Phase 1 pack is 12S1P Molicel P45B cells. Three IMUs are used, at the thigh, shank, and lower back.

### Lead packages

**ELEC-001 Bench power and stop path**
- Deliverable: bench power and stop path for the first actuator test. The exact stop condition is to be confirmed by the Project Leads.
- Shows it is done: a wiring diagram, plus the stop demonstrated before any motion.
- Drive folder: [Electrical](https://drive.google.com/drive/folders/1WLCSZ5bMisg1GjJH-oVJhsXjM938elaR)
- Owner: assigned by the Electrical lead.

**ELEC-003 DC-DC sizing**
- Deliverable: total 5 V and 3.3 V loads (Jetson Orin Nano, Teensy 4.1, IMUs, sensors), with the verified input-voltage requirement for each device.
- Shows it is done: a load table plus selected modules. The Jetson supply rail is to be confirmed by the Project Leads.
- Drive folder: [Electrical](https://drive.google.com/drive/folders/1WLCSZ5bMisg1GjJH-oVJhsXjM938elaR)
- Owner: assigned by the Electrical lead.

**ELEC-005 Wiring map and connector standard**
- Deliverable: wiring map, connector standard, CAN topology and termination.
- Shows it is done: a diagram.
- Drive folder: [Electrical](https://drive.google.com/drive/folders/1WLCSZ5bMisg1GjJH-oVJhsXjM938elaR)
- Owner: assigned by the Electrical lead.

### System Architecture and Controls

Drive folder: [System Architecture and Controls](https://drive.google.com/drive/folders/1J7P0P-SUsW-VQyd97wpCKYaZaU6DKhKf)

**ELEC-007** Electrical system block diagram showing the battery, power distribution, microcontrollers, sensors, motor drivers, and actuators. Shows it is done: the diagram file, with an update shown at the Tuesday session, planned Oct 27.

**ELEC-008** Preliminary control and communication architecture: how sensor information is processed and used to command the hip and knee actuators. Shows it is done: an architecture document with the sensor-to-actuator data path. The split between Electrical and Controls work is to be confirmed by the Project Leads.

**ELEC-009** List of required electrical interfaces: communication connections between controllers, sensors, and motor drivers. Shows it is done: an interface list reconciled to I-02, I-03, I-04, and I-06.

After delivery, the sub-team works with the Controls team to confirm that the electrical architecture supports the proposed control methods.

Owner for each package: assigned by the Electrical lead.

### Marcos' Disciples

Drive folder: [Marcos' Disciples](https://drive.google.com/drive/folders/1mtUqsmeW5VzTfu33sEIeIARAWhDKEwS4)

**ELEC-010** Sensor and microcontroller integration plan: how sensor data is collected and processed by the Teensy 4.1, and how sensor feedback supports closed-loop actuator control, coordinated with Controls. Shows it is done: a plan document reviewed with the Controls team.

**ELEC-011** Initial data acquisition setup: a method for recording sensor measurements and transmitting them to a computer. Shows it is done: a recorded sample data file captured from a Teensy-connected sensor.

**ELEC-012** GUI prototype that displays sample or live sensor data and reacts to it, using an ultrasonic sensor and a Teensy. It displays sensor readings, joint information, and system status. The GUI prototype does not command an actuator. Shows it is done: a screen recording or live demonstration of the GUI responding to the ultrasonic input.

Owner for each package: assigned by the Electrical lead.

### Kiboard Warriors

Drive folder: [Kiboard warriors](https://drive.google.com/drive/folders/1hG0fqPm67hvsPH7if0PFwHe7bgB8MXnZ)

**ELEC-013** Preliminary BMS integration concept: BMS functions and integration into the Phase 1 power system, with the relevant voltage, current, temperature, and battery protection parameters. The JK BMS is a candidate under study. Shows it is done: a concept document with a block diagram; a parameter table with a source for each row; each BMS function cited to a manufacturer document.

**ELEC-014** Battery monitoring and communication requirements: quantities monitored, update rates, transport from the BMS to the controller or monitoring interface, and behavior on loss of data. Includes a draft of I-08. Shows it is done: a numbered requirements list, and the I-08 draft reviewed with the Controls team.

**ELEC-015** Initial simulation or demonstration of battery monitoring behavior, with methods for simulating or testing BMS behavior, where feasible. Shows it is done: simulation output or a recorded log for each test case. A hardware demonstration additionally requires the lab safety courses on record for each participant and a BMS unit on hand.

Coordination at the Tuesday session. Owner for each package: assigned by the Electrical lead.

## Layout

```
schematics/    System and board schematics
pcb/           Board layouts (custom PCB is unbudgeted; Baseline §9)
harness/       Wiring map, connector standard, CAN topology and termination
sensors/       Encoders, IMUs, FSRs, load cell, power monitoring
power/         Bench supply and stop path, DC-DC rails, battery
datasheets/    Links to datasheets (no PDFs committed)
docs/          Power budget, test results
```

## How changes are made

Branch from `main`, open a pull request, get one approval from the code owner, merge. See `CONTRIBUTING.md`.

## Where files live

Native design files, bench logs, test data, photos, and vendor PDFs live in Drive. This repo holds exports, drawings, the BOM, code, and short summaries. PDF datasheets stay in Drive; `datasheets/` in this repo lists links.

Electrical: https://drive.google.com/drive/folders/1WLCSZ5bMisg1GjJH-oVJhsXjM938elaR

Sub-team folders inside the Electrical folder:
- System Architecture and Controls: https://drive.google.com/drive/folders/1J7P0P-SUsW-VQyd97wpCKYaZaU6DKhKf
- Marcos' Disciples: https://drive.google.com/drive/folders/1mtUqsmeW5VzTfu33sEIeIARAWhDKEwS4
- Kiboard warriors: https://drive.google.com/drive/folders/1hG0fqPm67hvsPH7if0PFwHe7bgB8MXnZ

Access is limited to EXO members. If the link says you need access, use Request access or ask your team lead.

## Safety

1. No powered actuator moves until the bench stop path has been demonstrated and the Project Leads have confirmed it.
2. Nobody wears any part of the device, including the battery belt, until the Project Leads confirm written approval.
3. No on-body sensor data, and no data from anyone wearing part of the device, goes into Drive or GitHub.
4. No lithium-ion pack assembly until a reviewed build procedure exists.
5. Lab work in ENG 208 requires the lab safety courses to be complete.
6. Never commit passwords, tokens, keys, or Wi-Fi credentials. Use an ignored file and a committed example file.
7. Nothing at battery pack voltage is connected to an actuator until the Project Leads confirm in writing that the actuator's allowed input voltage covers a full pack.
