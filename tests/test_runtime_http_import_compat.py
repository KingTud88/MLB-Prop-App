from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_HTTP = ROOT / "runtime_http.py"


def test_runtime_http_executes_without_sys_modules_registration():
    """Streamlit-style dynamic execution must not break ServiceFailure dataclass."""
    source = RUNTIME_HTTP.read_text(encoding="utf-8")
    module_name = "runtime_http_unregistered_loader_probe"
    sys.modules.pop(module_name, None)

    namespace = {
        "__name__": module_name,
        "__file__": str(RUNTIME_HTTP),
    }
    exec(compile(source, str(RUNTIME_HTTP), "exec"), namespace)

    failure = namespace["ServiceFailure"](
        service="MLB data",
        host="statsapi.mlb.com",
        method="GET",
        status_code=503,
        detail="probe",
    )
    assert failure.service == "MLB data"
    assert failure.status_code == 503
    assert module_name not in sys.modules
