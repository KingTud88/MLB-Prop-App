from __future__ import annotations

import ast
from pathlib import Path


def _get_log_node():
    source=Path("streamlit_app.py").read_text(encoding="utf-8")
    tree=ast.parse(source)
    return source,next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="get_log")


def test_get_log_does_not_use_streamlit_cache_replay():
    source,node=_get_log_node()
    assert not node.decorator_list
    calls=[ast.unparse(call.func) for call in ast.walk(node) if isinstance(call,ast.Call)]
    assert not any(name.startswith("st.") for name in calls)
    assert "_GAME_LOG_CACHE_TTL_SECONDS=1800" in source


def test_get_log_process_cache_returns_dataframe_copies():
    source,_=_get_log_node()
    assert "_GAME_LOG_CACHE.get(key)" in source
    assert "return cached[1].copy(),cached[2]" in source
    assert "_GAME_LOG_CACHE[key]=(now,result[0].copy(),result[1])" in source
