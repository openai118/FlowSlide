"""Normalize whitespace across Python files:
- strip trailing spaces on each line
- remove lines that contain only spaces
- remove trailing blank lines at EOF (ensure file ends with a single newline)

Run from repository root: python scripts/normalize_whitespace.py
"""
from pathlib import Path

EXCLUDE_DIRS = {".venv", "venv", "env", "__pycache__", "data", "temp"}
ROOT = Path(__file__).resolve().parents[1]

def should_skip(p: Path) -> bool:
    for part in p.parts:
        if part in EXCLUDE_DIRS:
            return True
    return False

changed_files = []
for p in ROOT.rglob('*.py'):
    if should_skip(p):
        continue
    try:
        text = p.read_text(encoding='utf-8')
    except Exception:
        try:
            text = p.read_text(encoding='latin-1')
        except Exception:
            continue
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        # remove trailing spaces
        stripped = line.rstrip()
        # convert lines that are only spaces to empty string
        if stripped == '':
            new_lines.append('')
        else:
            new_lines.append(stripped)
    # remove trailing blank lines
    while new_lines and new_lines[-1] == '':
        new_lines.pop()
    # ensure single newline at EOF
    new_text = '\n'.join(new_lines) + '\n'
    if new_text != text:
        p.write_text(new_text, encoding='utf-8')
        changed_files.append(str(p.relative_to(ROOT)))

print(f"Normalized whitespace in {len(changed_files)} files")
for f in changed_files:
    print(f)
