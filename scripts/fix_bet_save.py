from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

old = '''def _manual_line_options(market_key):
    if "outs" in str(market_key):
        return tuple(x + 0.5 for x in range(13, 19))
    if "hits_allowed" in str(market_key):
        return tuple(x + 0.5 for x in range(3, 9))
    return tuple(x + 0.5 for x in range(2, 12))'''

new = '''def _manual_line_options(market_key):
    market=str(market_key)
    # Important: "strikeouts" contains the substring "outs". Check the
    # explicit strikeout market first so K props never inherit outs lines.
    if "strikeouts" in market:
        return tuple(x + 0.5 for x in range(2, 12))
    if "pitcher_outs" in market:
        return tuple(x + 0.5 for x in range(13, 19))
    if "hits_allowed" in market:
        return tuple(x + 0.5 for x in range(3, 9))
    return tuple(x + 0.5 for x in range(2, 12))'''

if new in text:
    print("Manual market line routing already fixed.")
elif old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("Manual strikeout lines now use the K range instead of outs lines.")
else:
    raise SystemExit("Expected manual line option block was not found; refusing unsafe patch")
