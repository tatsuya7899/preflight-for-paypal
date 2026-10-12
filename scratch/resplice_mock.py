"""Re-splice the embedded verdict JSON inside panel_v6.html from verdict_F.json.

The mock file embeds the verdict object between the marker lines
` "verdict": {` and the closing ` }` + `};` of the DATA literal. Replaces that
block with the freshly generated verdict (new clause wording, fixed_status
rows, unfixable_for_order fields).
"""
import json
import os

HERE = os.path.dirname(__file__)
MOCK = os.path.join(HERE, "panel_v6.html")
VERDICT = os.path.join(HERE, "verdict_F.json")

with open(VERDICT) as f:
    data = json.load(f)

with open(MOCK) as f:
    lines = f.readlines()

start = next(i for i, l in enumerate(lines) if l.lstrip().startswith('"verdict":'))
# Find the line closing the verdict object by brace counting (strings in this
# file contain no braces, so a naive count is safe here).
depth = 0
end = None
for i in range(start, len(lines)):
    depth += lines[i].count("{") - lines[i].count("}")
    if depth == 0:
        end = i
        break
if end is None:
    raise SystemExit("verdict block close not found")

new_block = json.dumps(data["verdict"], indent=1, ensure_ascii=False).splitlines()
# keep the outer `"verdict": { ... }` wrapper format used by the file
replacement = [' "verdict": ' + new_block[0] + "\n"]
replacement += [l + "\n" for l in new_block[1:]]

lines[start:end + 1] = replacement

with open(MOCK, "w") as f:
    f.writelines(lines)
print(f"respliced lines {start + 1}-{end + 1}")
