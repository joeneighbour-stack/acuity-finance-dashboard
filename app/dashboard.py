"""Railway entry point for the existing Streamlit dashboard."""

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "dashboard.py"), run_name="__main__")
