#!/usr/bin/env python3
"""Generate the panel mock's data from the real implementation.

Runs rules.evaluate() + meaning.run() on the order_F fixture and dumps the
actual verdict JSON the extension would render. The mock must display this
output verbatim — no hand-typed check names, statuses, or evidence lists.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))

from backend import meaning, rules  # noqa: E402


def load(name):
    return json.loads((BACKEND / "fixtures" / name).read_text())


def main():
    order = load("order_F.json")
    # order_F's capture is PENDING/disputed and has no registered trackers.
    # Try the real trackers fixture if one was saved; otherwise empty.
    trackers_path = BACKEND / "fixtures" / "trackers_F.json"
    trackers = json.loads(trackers_path.read_text()) if trackers_path.exists() else []

    semantic = meaning.run(order)
    verdict = rules.evaluate(order, trackers, semantic)
    out = {
        "capture_id": "3J366679AY2283450",
        "order_id": "3UJ2460633408874H",
        "semantic": semantic,
        "verdict": verdict,
    }
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
