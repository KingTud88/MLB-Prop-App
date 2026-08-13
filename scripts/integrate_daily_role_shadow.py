from __future__ import annotations

from pathlib import Path

TARGET = Path("training/daily_projection_runner.py")

IMPORT_ANCHOR = "import requests\n"
IMPORT_LINE = "from training.daily_role_shadow import attach_daily_role_shadow, load_runtime_state\n"
OLD_INIT = "def run_daily_projections(day:str,**kwargs)->tuple[list[dict[str,Any]],list[str],int]:\n    games=get_schedule(day); records=[]; errors=[]; skipped=0; season=date.fromisoformat(day).year\n"
NEW_INIT = "def run_daily_projections(day:str,**kwargs)->tuple[list[dict[str,Any]],list[str],int]:\n    games=get_schedule(day); records=[]; errors=[]; skipped=0; season=date.fromisoformat(day).year; role_history=load_runtime_state()\n"
OLD_APPEND = "            records.append(project(game,log,**kwargs))\n"
NEW_APPEND = "            record=project(game,log,**kwargs)\n            records.append(attach_daily_role_shadow(record,log,game[\"game_time\"],role_history))\n"


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    changed = False
    if IMPORT_LINE not in text:
        if IMPORT_ANCHOR not in text:
            raise SystemExit("daily runner import anchor missing")
        text = text.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_LINE, 1)
        changed = True
    if NEW_INIT not in text:
        if OLD_INIT not in text:
            raise SystemExit("daily runner initialization anchor missing")
        text = text.replace(OLD_INIT, NEW_INIT, 1)
        changed = True
    if NEW_APPEND not in text:
        if OLD_APPEND not in text:
            raise SystemExit("daily runner append anchor missing")
        text = text.replace(OLD_APPEND, NEW_APPEND, 1)
        changed = True
    if changed:
        TARGET.write_text(text, encoding="utf-8")
    print("daily role workload shadow integration ready")


if __name__ == "__main__":
    main()
