#!/usr/bin/env python3
"""Run the metro_fragmentation_metrics notebook logic to regenerate metro_metrics.csv."""
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
nb_path = PROJECT_DIR / "metro_fragmentation_metrics.ipynb"

with open(nb_path) as f:
    nb = json.load(f)

globals_dict = {}
for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    source = "".join(cell.get("source", []))
    if not source.strip():
        continue
    try:
        exec(compile(source, "<notebook>", "exec"), globals_dict)
    except Exception as e:
        print(f"Error in cell: {e}", file=sys.stderr)
        raise

print("Done. metro_metrics.csv has been written.")
