"""Checks on the committed walkthrough notebook.

The notebook cannot be re-run in CI because the data is gitignored, so these tests guard what can be checked:
it must stay valid, its code must compile, it must keep the executed outputs GitHub displays, and those
outputs must show aggregated results only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "promo_profitability_walkthrough.ipynb"
RECORD_ID = re.compile(r"\b[TCP]\d{4,6}\b")  # transaction (T000001), customer (C00001) and product (P0001) ids


def _code_cells() -> list[dict]:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    return [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]


def test_notebook_code_compiles_and_has_no_stored_errors():
    cells = _code_cells()
    assert cells
    for number, cell in enumerate(cells, start=1):
        compile("".join(cell["source"]), f"code cell {number}", "exec")
        stored_errors = [output for output in cell["outputs"] if output["output_type"] == "error"]
        assert not stored_errors, f"code cell {number} stores an error"


def test_notebook_keeps_its_executed_outputs():
    cells = _code_cells()
    assert all(cell["execution_count"] for cell in cells)  # every code cell was run
    outputs = [output for cell in cells for output in cell["outputs"]]
    images = [output for output in outputs if "image/png" in output.get("data", {})]
    assert len(images) >= 4


def test_notebook_outputs_show_no_individual_records():
    for number, cell in enumerate(_code_cells(), start=1):
        for output in cell["outputs"]:
            texts = list(output.get("text", []))
            for mime_type, value in output.get("data", {}).items():
                if mime_type.startswith("text/"):
                    texts.extend(value)
            leaked = RECORD_ID.findall("".join(texts))
            assert not leaked, f"code cell {number} shows record ids such as {leaked[:3]}"
