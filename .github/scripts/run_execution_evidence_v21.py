from pathlib import Path
import runpy
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.execution_history import backfill_legacy_execution_sides

runpy.run_path(str(ROOT / ".github" / "scripts" / "execution_evidence_v21.py"), run_name="__main__")

archive_path = ROOT / "data" / "projection_archive.csv"
history_path = ROOT / "data" / "projection_log.csv"
archive = pd.read_csv(archive_path) if archive_path.exists() else pd.DataFrame()
history = pd.read_csv(history_path) if history_path.exists() else pd.DataFrame()
updated, recovered = backfill_legacy_execution_sides(archive, history)
updated.to_csv(archive_path, index=False)

outs = updated.get("manual_outs_side", pd.Series(index=updated.index, dtype=str)).fillna("").astype(str).str.upper()
hits = updated.get("manual_hits_allowed_side", pd.Series(index=updated.index, dtype=str)).fillna("").astype(str).str.upper()
print(f"legacy execution decisions recovered: {recovered}")
print(f"outs frozen/backfilled: {int(outs.isin(['OVER','UNDER','PASS']).sum())}")
print(f"hits frozen/backfilled: {int(hits.isin(['OVER','UNDER','PASS']).sum())}")
