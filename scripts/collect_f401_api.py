"""Collect F401 (imported but unused) violations under src/flowslide/api using flake8.
Writes JSON to scripts/f401_api.json with entries: {file, line, name, raw}
"""
import subprocess
import json
from pathlib import Path

p = subprocess.run(["python", "-m", "flake8", "src/flowslide/api", "--select=F401"], capture_output=True, text=True)
out = p.stdout + p.stderr
lines = [l for l in out.splitlines() if l.strip()]
entries = []
for l in lines:
    # expected format: path:line:col: F401 'name' imported but unused
    parts = l.split(":", 3)
    if len(parts) < 4:
        continue
    path = parts[0].strip()
    line_no = parts[1].strip()
    rest = parts[3].strip()
    # try to extract the name in quotes
    name = None
    import re
    m = re.search(r"'([^']+)' imported but unused", rest)
    if m:
        name = m.group(1)
    entries.append({"file": path, "line": int(line_no), "name": name, "raw": l})

out_path = Path(__file__).resolve().parent / "f401_api.json"
out_path.write_text(json.dumps(entries, indent=2), encoding='utf-8')
print(f"Found {len(entries)} F401 entries; wrote to {out_path}")
