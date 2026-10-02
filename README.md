# exo-electrical

Electrical design for the EXO Phase 1 leg: power, sensors, harness, and CAN wiring. Electrical owns sensor hardware, wiring, and connectors (Baseline §3).

| Field | Value |
| --- | --- |
| Owner | Electrical team lead (Luis) |
| Program | IEEE EXO, Phase 1 (unilateral prototype) |
| Current version | v0.1 (scaffold) |

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

## Drive folder

Electrical: https://drive.google.com/drive/folders/1WLCSZ5bMisg1GjJH-oVJhsXjM938elaR
Test Data: https://drive.google.com/drive/folders/13es75tDzfmytLOVGTCx-Fzi8i27h2tc4
Datasheets: https://drive.google.com/drive/folders/1lus-nHfzwbKOzzeUaEaSJ4TFtPrU0xcQ

PDF datasheets stay in Drive; `datasheets/` in this repo lists links.

Access is limited to EXO members. If the link says you need access, use Request access or ask your team lead.
