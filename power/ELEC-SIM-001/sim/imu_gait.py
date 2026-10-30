"""Measured gait timing from Shimmer IMU recordings (supplementary input).

Source
    archive.zip (Documents/usf/exo), Shimmer EXG units exported by
    ConsensysPRO as *_Calibrated_PC.csv, about 512 Hz. Per the archive's own
    Data Descriptions files:
        83AE  shank   CH1 gastrocnemius, CH2 tibialis anterior
        83B5  thigh   CH1 biceps femoris, CH2 rectus femoris
    Each file carries 3-axis accelerometer, 3-axis gyroscope and two EMG
    channels.

What this module is for
    The recordings carry no joint moments, force-plate data or anthropometrics,
    so they cannot replace the Moco XML that drives gaitctl.py. They give two
    things the Moco file cannot:
        1. measured stride time, from mid-swing peaks of the shank sagittal
           angular velocity, which sets the cadence range for cadence_study;
        2. measured knee angular velocity, thigh minus shank sagittal gyro,
           as a cross-check on the velocity side of the gait control model.

Data handling
    The archive is read in place (zip or extracted folder) and never copied
    into this package. Subject folders are named after real people, so every
    output carries an anonymous group id (G01, G02, ...) assigned by sorted folder
    order. A group is a folder, not a person: some folders hold several
    participants. No raw sample and no folder name leaves this module.

Assumptions (all in params.py with their tags)
    - The sagittal axis is the gyro axis with the largest variance on the shank.
    - Thigh and shank sagittal axes share a sign once aligned by correlation.
    - The gyro range is +/-500 deg/s; a stride containing a sample within 2%
      of it is clipped, and its peak angular velocity is a lower bound only.
"""
import io
import os
import re
import zipfile

import numpy as np

from .params import P

_FILE_RE = re.compile(r"Session(\d+)_Shimmer_([0-9A-Fa-f]{4})_Calibrated_PC\.csv$")


# ----------------------------------------------------------------- reading
def _iter_files(path):
    """(folder, filename, text) for every Calibrated_PC.csv in a zip or folder."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for name in sorted(z.namelist()):
                if _FILE_RE.search(name):
                    yield (os.path.dirname(name), os.path.basename(name),
                           z.read(name).decode("utf-8", errors="replace"))
    else:
        for root, _, files in sorted(os.walk(path)):
            for f in sorted(files):
                if _FILE_RE.search(f):
                    with open(os.path.join(root, f), encoding="utf-8", errors="replace") as fh:
                        yield os.path.relpath(root, path), f, fh.read()


def _parse(text, unit):
    """Time [s] and the 3 gyro axes [deg/s], or a reason the file is unusable."""
    lines = text.splitlines()
    if lines and lines[0].lower().startswith('"sep='):
        lines = lines[1:]
    if len(lines) < 3:
        return None, "fewer than three lines"
    delim = "\t" if "\t" in lines[0] else (";" if ";" in lines[0] else ",")
    names = [c.strip() for c in lines[0].split(delim)]
    want = ["Shimmer_%s_TimestampSync_Unix_CAL" % unit] + \
           ["Shimmer_%s_Gyro_%s_CAL" % (unit, a) for a in "XYZ"]
    try:
        cols = [names.index(w) for w in want]
    except ValueError:
        return None, "timestamp or gyro column missing (header re-saved by a spreadsheet)"
    try:
        d = np.loadtxt(io.StringIO("\n".join(lines[2:])), delimiter=delim,
                       usecols=cols, ndmin=2)
    except ValueError:
        return None, "non-numeric samples (locale-mangled by a spreadsheet re-save)"
    t = (d[:, 0] - d[0, 0]) / 1000.0
    dt = np.diff(t)
    if len(t) < 100 or not (0.0005 < np.median(dt) < 0.02):
        return None, "implausible sample interval"
    return (t, d[:, 1:4]), None


# ------------------------------------------------------------ signal tools
def _smooth(x, fs, f_c):
    """Zero-phase moving average, two passes; about -3 dB near f_c."""
    w = max(int(round(0.443 * fs / f_c)), 1)
    k = np.ones(w) / w
    y = np.convolve(x, k, mode="same")
    return np.convolve(y[::-1], k, mode="same")[::-1]


def _peaks(x, min_dist, height):
    """Local maxima above height, at least min_dist samples apart, greedy by size."""
    cand = np.flatnonzero((x[1:-1] > x[:-2]) & (x[1:-1] >= x[2:]) & (x[1:-1] > height)) + 1
    keep = []
    for i in cand[np.argsort(-x[cand])]:
        if all(abs(i - j) >= min_dist for j in keep):
            keep.append(i)
    return np.sort(np.asarray(keep, dtype=int))


def _sagittal(gyro):
    """Largest-variance axis, signed so the largest excursion is positive."""
    ax = int(np.argmax(gyro.std(axis=0)))
    g = gyro[:, ax]
    return (g if g.max() >= -g.min() else -g), "XYZ"[ax]


# ------------------------------------------------------------------ trial
def analyse_trial(shank, thigh=None):
    """Stride and knee figures for one session. shank/thigh are (t, gyro)."""
    t, gyro = shank
    fs = 1.0 / float(np.median(np.diff(t)))
    lim = 0.98 * P["imu_gyro_range_dps"]
    w_shank, axis = _sagittal(gyro)
    w_f = _smooth(w_shank, fs, P["imu_lowpass_hz"])

    pk = _peaks(w_f, int(P["imu_stride_min_s"] * fs), 0.4 * w_f.max())
    strides = np.diff(t[pk])
    ok = (strides >= P["imu_stride_min_s"]) & (strides <= P["imu_stride_max_s"])
    strides = strides[ok]

    out = {
        "fs_Hz": round(fs, 1),
        "duration_s": round(float(t[-1]), 2),
        "shank_sagittal_axis": axis,
        "n_strides": int(len(strides)),
        "stride_times_s": [round(float(s), 3) for s in strides],
        "shank_gyro_clipped": bool(np.any(np.abs(gyro) >= lim)),
        "peak_shank_omega_rad_s": round(float(np.radians(np.max(np.abs(w_shank)))), 2),
        "knee": None,
    }

    if thigh is not None:
        t2, gyro2 = thigh
        w_thigh = np.interp(t, t2, gyro2[:, int(np.argmax(gyro2.std(axis=0)))])
        if np.corrcoef(w_thigh, w_shank)[0, 1] < 0.0:
            w_thigh = -w_thigh
        w_knee = np.radians(_smooth(w_thigh - w_shank, fs, P["imu_lowpass_hz"]))
        clipped = bool(np.any(np.abs(gyro) >= lim) or np.any(np.abs(gyro2) >= lim))
        out["knee"] = {
            "peak_flexion_omega_rad_s": round(float(np.max(-w_knee)), 2),
            "peak_extension_omega_rad_s": round(float(np.max(w_knee)), 2),
            "peak_abs_omega_rad_s": round(float(np.max(np.abs(w_knee))), 2),
            "clipped_lower_bound_only": clipped,
        }
    return out


# ---------------------------------------------------------------- archive
def load_archive(path):
    """Analyse every session in the archive. Returns anonymised records only."""
    shank_u, thigh_u = P["imu_shank_unit"].upper(), P["imu_thigh_unit"].upper()
    sessions, rejected = {}, []
    for folder, fname, text in _iter_files(path):
        m = _FILE_RE.search(fname)
        session, unit = int(m.group(1)), m.group(2).upper()
        parsed, why = _parse(text, unit)
        key = (folder, session)
        if parsed is None:
            rejected.append((key, unit, why))
            continue
        sessions.setdefault(key, {})[unit] = parsed

    folders = sorted({k[0] for k in sessions} | {k[0][0] for k in rejected})
    anon = {f: "G%02d" % (i + 1) for i, f in enumerate(folders)}

    trials = []
    for (folder, session) in sorted(sessions, key=lambda k: (anon[k[0]], k[1])):
        units = sessions[(folder, session)]
        if shank_u not in units:
            rejected.append(((folder, session), thigh_u, "no shank unit in this session"))
            continue
        rec = analyse_trial(units[shank_u], units.get(thigh_u))
        rec = {"group": anon[folder], "session": session, **rec}
        trials.append(rec)

    return {
        "trials": trials,
        "rejected": [{"group": anon[k[0]], "session": k[1], "unit": u, "reason": why}
                     for k, u, why in rejected],
        "n_groups": len(folders),
    }


# ---------------------------------------------------------------- summary
def _pct(x, q):
    return round(float(np.percentile(x, q)), 3) if len(x) else None


def summarise(archive, model=None):
    """Pooled stride and knee statistics, with the Moco figures beside them."""
    trials = archive["trials"]
    strides = np.concatenate([np.asarray(t["stride_times_s"]) for t in trials]) \
        if trials else np.zeros(0)
    per_group = {}
    for t in trials:
        per_group.setdefault(t["group"], []).extend(t["stride_times_s"])

    knee = [t["knee"] for t in trials if t["knee"]]
    knee_clean = [k["peak_abs_omega_rad_s"] for k in knee if not k["clipped_lower_bound_only"]]
    knee_all = [k["peak_abs_omega_rad_s"] for k in knee]

    out = {
        "source": "Shimmer IMU archive, read in place, anonymised (recording folders G01 to G%02d)"
                  % archive["n_groups"],
        "n_groups": archive["n_groups"],
        "groups_are_not_people": ("A group is one top-level folder of the archive. Some "
                                  "folders hold several participants; the archive does not "
                                  "map sessions to participants reliably."),
        "n_trials_used": len(trials),
        "n_trials_with_strides": sum(1 for t in trials if t["n_strides"]),
        "n_files_rejected": len(archive["rejected"]),
        "n_strides": int(len(strides)),
        "stride_time_s": {"p10": _pct(strides, 10), "p25": _pct(strides, 25),
                          "median": _pct(strides, 50), "p75": _pct(strides, 75),
                          "p90": _pct(strides, 90),
                          "min": _pct(strides, 0), "max": _pct(strides, 100)},
        "cadence_strides_per_min_median": round(60.0 / float(np.median(strides)), 1)
        if len(strides) else None,
        "per_group_median_stride_s": {g: _pct(np.asarray(v), 50)
                                        for g, v in sorted(per_group.items()) if v},
        "trials_with_shank_gyro_clipped": sum(1 for t in trials if t["shank_gyro_clipped"]),
        "knee_trials": len(knee),
        "knee_trials_unclipped": len(knee_clean),
        "knee_peak_abs_omega_rad_s_unclipped": {"median": _pct(knee_clean, 50),
                                                "p90": _pct(knee_clean, 90)},
        "knee_peak_abs_omega_rad_s_all_lower_bound": {"median": _pct(knee_all, 50),
                                                      "p90": _pct(knee_all, 90)},
        "trials": trials,
        "rejected": archive["rejected"],
    }
    if model is not None:
        w = np.abs(model.omega[:, 1])
        out["moco_reference"] = {
            "cycle_s": round(model.cycle_s, 3),
            "weak_knee_peak_abs_omega_rad_s": round(float(w.max()), 2),
        }
    return out
