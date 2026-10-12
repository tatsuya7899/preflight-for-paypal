"""Print each fixture order's verdict summary (README table accuracy check)."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import rules

for k in "ABCDEF":
    with open(f"backend/fixtures/order_{k}.json") as f:
        o = json.load(f)
    v = rules.evaluate(o, [])
    fails = [c["condition"] for c in v["checks"] if c["status"] == "fail"]
    na = [c["condition"] for c in v["checks"] if c["status"] == "not_assessable"]
    print(k, v["order_id"], "| fails:", fails, "| n/a:", na)
