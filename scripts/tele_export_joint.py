"""Export the joint-model coefficients for the on-site "tea leaves" predictor: assets/data/tele_joint.json.

    python scripts/tele_analysis.py && python scripts/tele_joint.py && python scripts/tele_export_joint.py

Shape: lag, stats (mean and sd used to standardize PNA, ONI and PDO), mjo_freq (share of cold-season days in each MJO class,
0 = weak), and tiers -> metric -> term -> [coef, lo, hi] for the terms PNA, ONI, PDO and MJO1..MJO8 (relative to a weak MJO).
The page predicts the departure from an average day:  sum(b_i * z_i) + (c_phase - sum(f_k * c_k)),  so the intercept is not needed.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tele_analysis as ta  # noqa: E402

ROOT, RES = ta.ROOT, ta.RES
OUT = ROOT / "assets" / "data" / "tele_joint.json"
TIER = {"all stations": "all", "low (<4000 ft)": "low", "mid (4000-5000 ft)": "mid", "high (>=5000 ft)": "high"}


def main():
    st = json.loads((RES / "joint_stats.json").read_text())
    lag = st["lag"]
    z = np.load(RES / "panel.npz")
    idx = pd.DatetimeIndex(z["idx"])
    ta.PHASE_SHIFT = ta.phase_check()[0]
    ind, _ = ta.indices(idx, lag)
    mj = ind["mjo"].values
    freq = {str(k): round(float((mj == k).mean()), 4) for k in range(0, 9)}
    freq["0"] = round(1 - sum(v for k, v in freq.items() if k != "0"), 4)      # weak, or no OMI value
    R = pd.read_csv(RES / "joint_coefs.csv")
    R = R[(R["model"] == "joint") & R["unit"].isin(TIER) & (R["term"] != "intercept")]
    tiers = {}
    for r in R.itertuples():
        tiers.setdefault(TIER[r.unit], {}).setdefault(r.metric, {})[r.term] = [round(r.coef, 4), round(r.lo, 4), round(r.hi, 4)]
    out = {"generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}", "lag": lag, "stats": st["stats"], "mjo_freq": freq, "tiers": tiers,
           "period": "Nov-May, seasons 1992-2026, 36 SNOTEL stations"}
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print("wrote", OUT, OUT.stat().st_size // 1024, "KB", freq)


if __name__ == "__main__":
    main()
