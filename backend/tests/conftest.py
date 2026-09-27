"""Pin Demo Mode data to the fixed synthetic seed (data/seed) so tests don't depend on pipeline runs."""

import os
from pathlib import Path

os.environ["PC_DEMO_DIR"] = str(Path(__file__).resolve().parents[1] / "data" / "seed")
