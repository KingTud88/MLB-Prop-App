from pathlib import Path

ENGINE = Path("engine/research_promotion_scoreboard.py")
TEST = Path("tests/test_research_promotion_scoreboard_ui_contract.py")

text = ENGINE.read_text(encoding="utf-8")

old_css = '''        .research-card{min-height:245px;margin:.32rem 0;padding:.78rem .84rem;border:1px solid rgba(77,108,137,.68);border-radius:14px;background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98));box-shadow:0 10px 24px rgba(0,0,0,.18)}
        .research-card-top{display:flex;gap:.6rem;align-items:center;justify-content:space-between}
        .research-card-lane{color:#f3f7fa;font:900 .90rem/1.2 system-ui;text-transform:uppercase;letter-spacing:.035em}
        .research-pill{padding:.20rem .46rem;border-radius:999px;font:900 .62rem/1.2 system-ui;letter-spacing:.05em;text-transform:uppercase;white-space:nowrap}
        .research-good{color:#86efac;border:1px solid rgba(34,197,94,.55);background:rgba(34,197,94,.13)}
        .research-bad{color:#ff8a9a;border:1px solid rgba(255,54,85,.58);background:rgba(227,25,55,.14)}
        .research-watch{color:#ffd166;border:1px solid rgba(250,204,21,.48);background:rgba(250,204,21,.10)}
        .research-neutral{color:#9fb3c6;border:1px solid rgba(159,179,198,.38);background:rgba(159,179,198,.08)}
        .research-label{margin-top:.56rem;color:#7fa4c2;font:900 .59rem/1.2 system-ui;letter-spacing:.09em;text-transform:uppercase}
        .research-value{margin-top:.09rem;color:#dfe9f0;font:720 .76rem/1.38 system-ui}
        .research-authority{color:#ff8a9a;font-weight:900}
        @media(max-width:700px){.research-card{min-height:0}.research-card-top{align-items:flex-start;flex-direction:column}}
'''

new_css = '''        .research-card{min-height:198px;margin:.24rem 0;padding:.64rem .76rem .58rem;border:1px solid rgba(77,108,137,.68);border-radius:14px;background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98));box-shadow:0 10px 24px rgba(0,0,0,.18)}
        .research-card-top{display:flex;gap:.6rem;align-items:center;justify-content:space-between;margin-bottom:.10rem}
        .research-card-lane{color:#f3f7fa;font:900 .90rem/1.2 system-ui;text-transform:uppercase;letter-spacing:.035em}
        .research-pill{padding:.20rem .46rem;border-radius:999px;font:900 .62rem/1.2 system-ui;letter-spacing:.05em;text-transform:uppercase;white-space:nowrap}
        .research-good{color:#86efac;border:1px solid rgba(34,197,94,.55);background:rgba(34,197,94,.13)}
        .research-bad{color:#ff8a9a;border:1px solid rgba(255,54,85,.58);background:rgba(227,25,55,.14)}
        .research-watch{color:#ffd166;border:1px solid rgba(250,204,21,.48);background:rgba(250,204,21,.10)}
        .research-neutral{color:#9fb3c6;border:1px solid rgba(159,179,198,.38);background:rgba(159,179,198,.08)}
        .research-label{margin-top:.38rem;color:#7fa4c2;font:900 .57rem/1.15 system-ui;letter-spacing:.09em;text-transform:uppercase}
        .research-value{margin-top:.06rem;color:#dfe9f0;font:720 .73rem/1.30 system-ui}
        .research-label-sample{color:#6f93b0}
        .research-value-sample{color:#b8c8d5;font-weight:680}
        .research-label-gate{margin-top:.40rem;color:#91c6eb}
        .research-value-gate{margin-top:.09rem;padding:.26rem .36rem;border-left:2px solid #38bdf8;border-radius:7px;background:rgba(56,189,248,.055);color:#f4f8fb;font:900 .78rem/1.30 system-ui}
        .research-label-action{color:#7899b4}
        .research-value-action{color:#c8d5df;font-weight:760}
        .research-authority-strip{display:flex;align-items:center;justify-content:space-between;gap:.6rem;margin-top:.48rem;padding:.30rem .42rem;border-top:1px solid rgba(255,54,85,.30);border-radius:7px;background:rgba(105,14,33,.10)}
        .research-authority-label{color:#7595ae;font:900 .56rem/1.15 system-ui;letter-spacing:.085em;text-transform:uppercase}
        .research-authority{color:#ff8a9a;font:900 .68rem/1.15 system-ui;letter-spacing:.035em;text-transform:uppercase}
        @media(max-width:700px){.research-card{min-height:0}.research-card-top{align-items:flex-start;flex-direction:column}.research-authority-strip{align-items:flex-start}}
'''

if old_css not in text:
    raise SystemExit("expected research scoreboard CSS block not found")
text = text.replace(old_css, new_css, 1)

old_html = '''                    '<div class="research-label">Sample</div>'
                    f'<div class="research-value">{escape(_text(row["Sample"]))}</div>'
                    '<div class="research-label">Gate progress</div>'
                    f'<div class="research-value">{escape(_text(row["Gate Progress"]))}</div>'
                    '<div class="research-label">Current signal</div>'
                    f'<div class="research-value">{escape(_text(row["Signal"]))}</div>'
                    '<div class="research-label">Action</div>'
                    f'<div class="research-value">{escape(_text(row["Recommended Action"]))}</div>'
                    '<div class="research-label">Production authority</div>'
                    f'<div class="research-value research-authority">{escape(_text(row["Production Authority"]))}</div>'
'''

new_html = '''                    '<div class="research-label research-label-sample">Sample</div>'
                    f'<div class="research-value research-value-sample">{escape(_text(row["Sample"]))}</div>'
                    '<div class="research-label research-label-gate">Gate progress</div>'
                    f'<div class="research-value research-value-gate">{escape(_text(row["Gate Progress"]))}</div>'
                    '<div class="research-label">Current signal</div>'
                    f'<div class="research-value">{escape(_text(row["Signal"]))}</div>'
                    '<div class="research-label research-label-action">Action</div>'
                    f'<div class="research-value research-value-action">{escape(_text(row["Recommended Action"]))}</div>'
                    '<div class="research-authority-strip">'
                    '<span class="research-authority-label">Production authority</span>'
                    f'<span class="research-authority">{escape(_text(row["Production Authority"]))}</span>'
                    '</div>'
'''

if old_html not in text:
    raise SystemExit("expected research scoreboard card HTML block not found")
text = text.replace(old_html, new_html, 1)
ENGINE.write_text(text, encoding="utf-8")

test = TEST.read_text(encoding="utf-8")
addition = '''\n\ndef test_research_scoreboard_density_polish_keeps_gate_progress_primary_and_authority_compact() -> None:\n    text = Path("engine/research_promotion_scoreboard.py").read_text(encoding="utf-8")\n    assert ".research-card{min-height:198px" in text\n    assert "research-label-gate" in text\n    assert "research-value-gate" in text\n    assert "research-authority-strip" in text\n    assert '<span class="research-authority-label">Production authority</span>' in text\n    assert "research-value-sample" in text\n    assert "research-value-action" in text\n'''
if "test_research_scoreboard_density_polish_keeps_gate_progress_primary_and_authority_compact" not in test:
    test += addition
TEST.write_text(test, encoding="utf-8")
