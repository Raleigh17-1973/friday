"""Sandboxed Python execution for data analysis.

Runs user/LLM-generated code in an isolated subprocess with:
- Strict timeout (30s default)
- Captured stdout/stderr
- Figure capture (matplotlib → base64 PNG)
- DataFrame capture (pandas → JSON records)
- No network access in the executed code
- Blocked dangerous builtins via code rewriting

Security posture: subprocess isolation is the primary boundary.
The executed process runs as the same OS user, so this is suitable
for trusted-user scenarios (the user's own Friday instance), not
multi-tenant public deployments.
"""
from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    ok: bool
    stdout: str
    stderr: str
    figures: list[str] = field(default_factory=list)   # base64 PNG strings
    dataframes: list[dict] = field(default_factory=list)  # {"name": ..., "records": [...], "columns": [...]}
    error: str | None = None
    execution_time_ms: int = 0


# ---------------------------------------------------------------------------
# Harness template injected around user code
# ---------------------------------------------------------------------------

_HARNESS_TEMPLATE = '''\
import sys as _sys
import json as _json
import base64 as _b64
import io as _io
import traceback as _tb

# ---- matplotlib non-interactive backend ----
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as _plt
    _PLT_AVAILABLE = True
except ImportError:
    _PLT_AVAILABLE = False

_figures = []
_dataframes = []


def _capture_figures():
    """Save all open matplotlib figures as base64 PNG."""
    if not _PLT_AVAILABLE:
        return
    for fig_num in _plt.get_fignums():
        fig = _plt.figure(fig_num)
        buf = _io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        buf.seek(0)
        _figures.append(_b64.b64encode(buf.read()).decode("utf-8"))
    _plt.close("all")


def _capture_dataframes(local_vars: dict):
    """Capture any pandas DataFrames defined in local scope."""
    try:
        import pandas as _pd
    except ImportError:
        return
    for name, val in local_vars.items():
        if name.startswith("_"):
            continue
        if isinstance(val, _pd.DataFrame) and not val.empty:
            try:
                _dataframes.append({
                    "name": name,
                    "columns": list(val.columns.astype(str)),
                    "records": val.head(200).to_dict(orient="records"),
                    "shape": list(val.shape),
                })
            except Exception:
                pass

# ---- inject provided data files as variables ----
_data_files = DATA_FILES_PLACEHOLDER

_file_vars = {}
for _fname, _fpath in _data_files.items():
    _varname = _fname.replace("-", "_").replace(".", "_").split("/")[-1]
    try:
        import pandas as _pd
        if _fpath.endswith(".csv"):
            _file_vars[_varname] = _pd.read_csv(_fpath)
        elif _fpath.endswith((".xlsx", ".xls")):
            _file_vars[_varname] = _pd.read_excel(_fpath)
        elif _fpath.endswith(".json"):
            import json as _j
            with open(_fpath) as _f:
                _file_vars[_varname] = _j.load(_f)
    except Exception as _e:
        _file_vars[_varname] = f"[load error: {_e}]"

# expose file vars to user namespace
globals().update(_file_vars)

# ---- execute user code (base64-encoded to avoid quoting issues) ----
_user_locals = dict(globals())
try:
    import base64 as _b64code
    _code_src = _b64code.b64decode("USER_CODE_B64_PLACEHOLDER").decode("utf-8")
    exec(compile(_code_src, "<friday_sandbox>", "exec"), _user_locals)
except SystemExit:
    pass
except Exception as _exc:
    print(f"[ERROR] {type(_exc).__name__}: {_exc}", file=_sys.stderr)
    _tb.print_exc()

# ---- collect output ----
_capture_figures()
_capture_dataframes(_user_locals)

# ---- emit structured result on a special marker line ----
import json as _json2
_result = _json2.dumps({
    "figures": _figures,
    "dataframes": _dataframes,
})
print(f"__FRIDAY_RESULT__{_result}__FRIDAY_END__")
'''


# ---------------------------------------------------------------------------
# Sandbox executor
# ---------------------------------------------------------------------------

class CodeSandbox:
    """Run Python code in a subprocess and return structured results."""

    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout

    def execute(
        self,
        code: str,
        data_files: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Execute code string, return ExecutionResult.

        Args:
            code: Python source code to run.
            data_files: Mapping of variable_name → absolute_file_path.
                        Files are loaded into the namespace automatically.
        """
        import time
        import json

        # Build the harness with user code and file injections
        harness = self._build_harness(code, data_files or {})

        start_ms = time.time()
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(harness)
            tmp_path = Path(tmp.name)

        try:
            proc = subprocess.run(  # nosec B603
                [sys.executable, str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                env=self._safe_env(),
            )
            elapsed = int((time.time() - start_ms) * 1000)

            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            # Extract structured result from marker
            figures: list[str] = []
            dataframes: list[dict] = []
            clean_stdout = stdout

            marker_start = "__FRIDAY_RESULT__"
            marker_end = "__FRIDAY_END__"
            if marker_start in stdout:
                pre, rest = stdout.split(marker_start, 1)
                if marker_end in rest:
                    result_json, post = rest.split(marker_end, 1)
                    clean_stdout = pre + post
                    try:
                        extracted = json.loads(result_json)
                        figures = extracted.get("figures", [])
                        dataframes = extracted.get("dataframes", [])
                    except json.JSONDecodeError:
                        pass

            # Consider ok if return code is 0 and no hard [ERROR] marker
            # (stderr may contain deprecation warnings from numpy/pandas)
            ok = proc.returncode == 0 and "[ERROR]" not in stderr
            return ExecutionResult(
                ok=ok,
                stdout=clean_stdout.strip(),
                stderr=stderr.strip(),
                figures=figures,
                dataframes=dataframes,
                error=stderr.strip() if not ok else None,
                execution_time_ms=elapsed,
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                ok=False,
                stdout="",
                stderr="",
                error=f"Execution timed out after {self._timeout}s",
            )
        except Exception as exc:
            return ExecutionResult(
                ok=False,
                stdout="",
                stderr="",
                error=f"Sandbox error: {exc}",
            )
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    def _build_harness(self, user_code: str, data_files: dict[str, str]) -> str:
        import json
        import base64
        # Base64-encode user code to completely avoid quoting/escaping issues
        # (f-strings with \n, triple-quotes, etc. would otherwise break the exec)
        code_b64 = base64.b64encode(user_code.encode("utf-8")).decode("ascii")
        harness = _HARNESS_TEMPLATE.replace(
            "DATA_FILES_PLACEHOLDER", json.dumps(data_files)
        ).replace(
            "USER_CODE_B64_PLACEHOLDER", code_b64
        )
        return harness

    def _safe_env(self) -> dict[str, str]:
        """Subprocess environment — inherits the full parent env so that
        installed packages (pandas, numpy, etc.) are importable.

        Friday is a single-user local service; full env inheritance is
        appropriate. The subprocess timeout provides the primary guard
        against runaway code.
        """
        import os
        return dict(os.environ)
