from pathlib import Path

path = Path("pages/4_Projection_History.py")
text = path.read_text(encoding="utf-8")
old = 'st.caption("Lineup, workload, rest, history source, opponent K/contact environments are model inputs. Team Leash Candidate and Weather Delay Risk are CONTEXT ONLY and do not modify the baseball forecast.")'
new = 'st.caption("Lineup, workload, rest, history source, opponent K/contact environments are model inputs. Team Leash Candidate is CONTEXT ONLY and does not modify the baseball forecast. Weather Delay Risk is labeled CONTEXT ONLY because weather still does not modify the baseball forecast.")'
if old not in text:
    raise SystemExit("combined context-only caption anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
