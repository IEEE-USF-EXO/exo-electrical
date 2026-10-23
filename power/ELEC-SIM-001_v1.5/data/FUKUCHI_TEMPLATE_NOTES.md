# Fukuchi gait template used by v2.2

Author/creator metadata: Gustavorodriguezpc

The v2.2 baseline uses a 101-point engineering representation of the sagittal-plane healthy-young overground walking curves reported in:

Fukuchi, C. A., Fukuchi, R. K., Duarte, M. (2018), *A public dataset of overground and treadmill walking kinematics and kinetics in healthy individuals*, PeerJ 6:e4640, DOI 10.7717/peerj.4640. Dataset DOI 10.6084/m9.figshare.5722711.

The public WBDS dataset contains time-normalized processed kinematic and kinetic data. The bundled CSV follows the published young-group slow / comfortable / fast overground waveform ranges and shapes at 0-100% gait cycle. It is an engineering representation used for battery/actuator sizing and is **not a verbatim export of one WBDS participant file**.

For exact study reproduction, download the WBDS processed ASCII data and WBDSinfo.xlsx, select the young healthy overground trials, compute the group ensemble average at the desired speed, and export these five columns:

- `phase_pct`
- `hip_angle_deg`
- `knee_angle_deg`
- `hip_moment_Nm_per_kg`
- `knee_moment_Nm_per_kg`

Then set `user.custom_gait_csv` in `user_inputs.m` to that file. The rest of the electrical model does not change.
