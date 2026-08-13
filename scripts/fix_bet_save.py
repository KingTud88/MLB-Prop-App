from pathlib import Path

p = Path("pages/6_Top_Plays.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
    'view = plays[["Rank", "Pitcher", "Weather Icon", "Market", "Side", "Line", "Projection", "Model Probability", "Status", "Weather Risk", "Data Quality", "Book", "Odds"]].copy()',
    'view = plays[["Rank", "Pitcher", "Weather Icon", "Market", "Side", "Line", "Projection", "Model Probability", "Weather Risk", "Decision Evidence", "Signal Evidence", "Tier Hit Rate"]].copy()',
    1,
)
s = s.replace(
    'view["Pitcher"] = view.apply(lambda r: f"{r[\'Pitcher\']} {str(r.get(\'Weather Icon\', \'\') or \'\')}".strip(), axis=1)',
    'view["Pitcher"] = view.apply(lambda r: f"{r[\'Pitcher\']} {\'\' if pd.isna(r.get(\'Weather Icon\')) else str(r.get(\'Weather Icon\') or \'\')}".strip(), axis=1)',
    1,
)
if 'view["Tier Hit Rate"] = view["Tier Hit Rate"].map' not in s:
    s = s.replace(
        'view["Projection"] = view["Projection"].map(lambda x: f"{float(x):.2f}")',
        'view["Projection"] = view["Projection"].map(lambda x: f"{float(x):.2f}")\nview["Tier Hit Rate"] = view["Tier Hit Rate"].map(lambda x: "—" if x is None or pd.isna(x) else f"{float(x):.1%}")',
        1,
    )
s = s.replace('view["Book"] = view["Book"].map(lambda x: x if str(x).strip() else "—")\n', '', 1)
s = s.replace('view["Odds"] = view["Odds"].map(lambda x: "—" if pd.isna(x) else f"{int(float(x)):+d}")\n', '', 1)

old = '''event = st.dataframe(
    view,
    hide_index=True,
    use_container_width=True,
    key="top_plays_selectable",
    on_select="rerun",
    selection_mode="single-row",
)'''
new = '''styled_view = view.style.set_properties(
    subset=["Projection"],
    **{"background-color":"rgba(93,48,128,.42)","color":"#ffffff","font-weight":"900","border-left":"1px solid #8b4fc7","border-right":"1px solid #8b4fc7"},
)
event = st.dataframe(
    styled_view,
    hide_index=True,
    use_container_width=True,
    key="top_plays_selectable",
    on_select="rerun",
    selection_mode="single-row",
)'''
s = s.replace(old, new, 1)

old_card = '''        weather_icon = str(play_row.get("Weather Icon", "") or "")
        st.markdown(f"### #{rank} · {play_row['Pitcher']} {weather_icon}".strip())
        st.markdown(f"**{play_row['Market']} · {play_row['Side']} {float(play_row['Line']):g}**")
        st.markdown(f"Projection **{float(play_row['Projection']):.2f}** · Model **{float(play_row['Model Probability']):.1%}**")
        st.caption(f"{play_row.get('Status', 'MODEL PLAY')} · {play_row.get('Model Health', 'LEARNING')} health · evidence in View details")'''
new_card = '''        weather_raw = play_row.get("Weather Icon", "")
        weather_icon = "" if pd.isna(weather_raw) else str(weather_raw or "")
        team_raw = play_row.get("Team", "")
        team = "" if pd.isna(team_raw) else str(team_raw or "")
        st.markdown(f"### #{rank} · {play_row['Pitcher']} {weather_icon}".strip())
        if team:
            st.caption(team)
        st.markdown(f"**{play_row['Market']} · {play_row['Side']} {float(play_row['Line']):g}**")
        st.markdown(f"**PROJECTION · {float(play_row['Projection']):.2f}**  |  **MODEL · {float(play_row['Model Probability']):.1%}**")
        tier_hit = numeric(play_row.get("Tier Hit Rate"))
        st.caption(f"Tier Hit Rate: {'—' if tier_hit is None else f'{tier_hit:.1%}'}")'''
s = s.replace(old_card, new_card, 1)

anchor = 'st.markdown("---")\nst.subheader("🎟️ Parlay Builder")'
if 'Projections are model estimates at the listed line.' not in s:
    s = s.replace(anchor, 'st.caption("ⓘ Projections are model estimates at the listed line. They are not guaranteed outcomes.")\n\n' + anchor, 1)

p.write_text(s, encoding="utf-8")
print("Top Plays approved layout patched.")
