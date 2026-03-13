"""CodeInterpreterService — high-level interface for data analysis."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from packages.interpreter.sandbox import CodeSandbox, ExecutionResult

_log = logging.getLogger(__name__)


class CodeInterpreterService:
    """High-level service that wraps the sandbox for Friday tool calls.

    Handles:
    - Running analysis code against uploaded files
    - Generating summary text from results
    - Storing generated figures via FileStorageService (optional)
    """

    def __init__(
        self,
        storage=None,  # Optional[FileStorageService]
        timeout: int = 30,
    ) -> None:
        self._sandbox = CodeSandbox(timeout=timeout)
        self._storage = storage

    def run(
        self,
        code: str,
        data_files: dict[str, str] | None = None,
        org_id: str = "org-1",
    ) -> dict[str, Any]:
        """Execute code and return a tool-friendly result dict.

        Returns:
            {
                "ok": bool,
                "output": str,          # stdout
                "error": str | None,
                "dataframes": [...],    # captured DataFrames as records
                "figure_ids": [...],    # file IDs of stored PNG figures
                "execution_time_ms": int,
            }
        """
        result: ExecutionResult = self._sandbox.execute(code, data_files=data_files)

        # Store figures in FileStorageService if available
        figure_ids: list[str] = []
        if self._storage and result.figures:
            import base64
            for i, fig_b64 in enumerate(result.figures):
                try:
                    png_bytes = base64.b64decode(fig_b64)
                    stored = self._storage.store(
                        content=png_bytes,
                        filename=f"figure_{i + 1}.png",
                        mime_type="image/png",
                        org_id=org_id,
                        created_by="code_interpreter",
                        metadata={"source": "code_interpreter", "figure_index": i},
                    )
                    figure_ids.append(stored.file_id)
                except Exception as exc:
                    _log.warning("Failed to store figure %d: %s", i, exc)

        return {
            "ok": result.ok,
            "output": result.stdout,
            "error": result.error,
            "dataframes": result.dataframes,
            "figure_ids": figure_ids,
            "figures_b64": result.figures if not figure_ids else [],  # inline if no storage
            "execution_time_ms": result.execution_time_ms,
        }

    def analyze_file(
        self,
        file_path: str | Path,
        question: str,
        org_id: str = "org-1",
    ) -> dict[str, Any]:
        """Generate and run analysis code for a natural-language question about a file.

        This generates a simple exploratory analysis when no LLM is available.
        When an LLM is wired in, the caller should generate the code itself.
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        varname = path.stem.replace("-", "_").replace(" ", "_")

        if ext == ".csv":
            load_line = f'{varname} = pd.read_csv(r"{path}")'
        elif ext in (".xlsx", ".xls"):
            load_line = f'{varname} = pd.read_excel(r"{path}")'
        elif ext == ".json":
            load_line = f'import json; {varname} = pd.DataFrame(json.load(open(r"{path}")))'
        else:
            return {"ok": False, "error": f"Unsupported file type: {ext}", "output": ""}

        code = f"""\
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

{load_line}
df = {varname}

print(f"Shape: {{df.shape}}")
print("\\nColumn types:")
print(df.dtypes)
print("\\nFirst 5 rows:")
print(df.head())
print("\\nDescriptive statistics:")
print(df.describe(include='all').to_string())

# Auto-plot numeric columns
numeric_cols = df.select_dtypes(include='number').columns.tolist()
if numeric_cols:
    fig, axes = plt.subplots(1, min(len(numeric_cols), 3), figsize=(15, 4))
    if len(numeric_cols) == 1:
        axes = [axes]
    for ax, col in zip(axes if hasattr(axes, '__iter__') else [axes], numeric_cols[:3]):
        df[col].dropna().hist(ax=ax, bins=20, edgecolor='black', color='steelblue')
        ax.set_title(col)
        ax.set_xlabel(col)
        ax.set_ylabel('Frequency')
    plt.tight_layout()
    plt.savefig('/tmp/analysis_hist.png', dpi=100, bbox_inches='tight')
"""
        return self.run(code, org_id=org_id)

    def generate_analysis_code(self, question: str, file_info: dict) -> str:
        """Return a boilerplate analysis template for a question + file.

        In production, this would be replaced by an LLM-generated code block.
        """
        varname = Path(file_info.get("filename", "data.csv")).stem.replace("-", "_")
        return f"""\
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Data is pre-loaded as: {varname} (DataFrame)
df = {varname}

# Analysis for: {question}
print(f"Dataset: {{df.shape[0]}} rows × {{df.shape[1]}} columns")
print("\\nColumns:", list(df.columns))
print("\\nSummary statistics:")
print(df.describe())

# TODO: Add specific analysis for the question above
"""
