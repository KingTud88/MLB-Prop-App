from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
nav_path = ROOT / "navigation.py"
text = nav_path.read_text(encoding="utf-8")

# Remove the retired page-link sidebar stylesheet at the top of render_sidebar.
# The Projection-parity V3 radio shell below is now the single sidebar owner.
fn = 'def render_sidebar(active: str = "projection") -> None:\n    """Render the shared Cleveland-night app navigation."""\n'
if fn not in text:
    raise SystemExit("render_sidebar anchor not found")
fn_pos = text.index(fn) + len(fn)
old_start = text.index("    st.markdown(\n", fn_pos)
old_end = text.index('    if active == "top":\n', old_start)
text = text[:old_start] + text[old_end:]

old = '        [data-testid="stSidebar"] .cc-sidebar-brand{margin:.10rem 0 .80rem!important}\n'
new = '''        [data-testid="stSidebar"] .cc-sidebar-brand{
            padding:.85rem .7rem .8rem!important;
            margin:.10rem 0 .80rem!important;
            border:1px solid rgba(78,108,137,.66)!important;
            border-radius:14px!important;
            background:linear-gradient(145deg,rgba(8,29,51,.98),rgba(3,16,30,.98))!important;
            text-align:center!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 12px 26px rgba(0,0,0,.20)!important;
        }
        [data-testid="stSidebar"] .cc-sidebar-crown{color:#ec1638!important;font-size:1.2rem!important;line-height:1!important}
        [data-testid="stSidebar"] .cc-sidebar-script{color:#f5f1e9!important;font-family:Georgia,"Times New Roman",serif!important;font-size:1.55rem!important;font-weight:800!important;font-style:italic!important;line-height:.95!important}
        [data-testid="stSidebar"] .cc-sidebar-king{color:#ec1638!important;font-family:Impact,"Arial Narrow",sans-serif!important;font-size:1.42rem!important;letter-spacing:.035em!important;line-height:1!important;text-transform:uppercase!important}
        [data-testid="stSidebar"] .cc-sidebar-tag{margin-top:.38rem!important;color:#9fb3c5!important;font:700 .78rem/1.35 system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important}
'''
if old not in text:
    raise SystemExit("V3 brand margin anchor not found")
text = text.replace(old, new, 1)
nav_path.write_text(text, encoding="utf-8")

# Tight source contract: no retired fixed-width/page-link rail remains.
test_path = ROOT / "tests" / "test_ui_theme_contract.py"
test = test_path.read_text(encoding="utf-8")
needle = '    assert "👑" not in rendered\n'
extra = '''    assert "width: 252px !important" not in source
    assert "sk-page-link" not in source
    assert "cc-sidebar-script" in source
    assert "cc-sidebar-king" in source
'''
if extra.strip() not in test:
    if needle not in test:
        raise SystemExit("sidebar parity test insertion anchor not found")
    test = test.replace(needle, needle + extra, 1)
test_path.write_text(test, encoding="utf-8")
print("sidebar_shell_cleanup_v17 applied")
