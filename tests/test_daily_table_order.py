from pathlib import Path


def test_daily_projection_table_keeps_k_projection_near_pitcher():
    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    block_start = source.index("display_cols = [", source.index("if not slate.empty:"))
    block_end = source.index("]", block_start)
    block = source[block_start:block_end]
    assert block.index('"player"') < block.index('"team"') < block.index('"opponent"') < block.index('"projection"')
    assert block.index('"projection"') < block.index('"weather_delay_risk"')
    assert block.index('"projection"') < block.index('"starter_history_games"')
    assert block.index('"projection"') < block.index('"workload_version"')
    assert block.index('"sim_5p"') < block.index('"weather_delay_risk"')
