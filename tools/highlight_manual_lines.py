from pathlib import Path

path = Path("pages/5_Daily_Projection_Run.py")
text = path.read_text(encoding="utf-8")

old = '''        styled_display = display.style.format(formatters, na_rep="—")
        if projection_highlight_cols:
            styled_display = styled_display.map(
                lambda value: "color: #22c55e; font-weight: 700;" if pd.notna(value) else "",
                subset=projection_highlight_cols,
            )
'''

new = '''        styled_display = display.style.format(formatters, na_rep="—")
        if projection_highlight_cols:
            styled_display = styled_display.map(
                lambda value: "color: #22c55e; font-weight: 700;" if pd.notna(value) else "",
                subset=projection_highlight_cols,
            )

        # Make user-entered execution lines immediately visible without
        # changing the frozen projection layer. Paid/API lines keep the
        # standard table styling; MANUAL lines get the orange treatment.
        manual_line_styles = pd.DataFrame("", index=display.index, columns=display.columns)
        for line_col, source_col in (
            ("K Line", "K Source"),
            ("Outs Line", "Outs Source"),
            ("Hits Line", "Hits Source"),
        ):
            if line_col not in display.columns or source_col not in display.columns:
                continue
            manual_mask = (
                display[source_col].fillna("").astype(str).str.upper().eq("MANUAL")
                & display[line_col].notna()
            )
            manual_line_styles.loc[manual_mask, line_col] = (
                "color: #ff9f1c; font-weight: 800; background-color: rgba(255,159,28,.12);"
            )
            manual_line_styles.loc[manual_mask, source_col] = "color: #ff9f1c; font-weight: 800;"
        styled_display = styled_display.apply(lambda _: manual_line_styles, axis=None)
'''

if new in text:
    print("Manual-line highlight already applied")
elif old not in text:
    raise SystemExit("Could not find Starter Slate styling anchor")
else:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("Applied orange MANUAL-line highlight")
