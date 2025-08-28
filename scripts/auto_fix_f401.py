"""
Conservative auto-fixer for flake8 F401 (imported but unused).

Behavior:
- Run flake8 --select=F401 on the repository (src/flowslide).
- For each F401 entry, extract file path and imported name.
- Search the workspace for occurrences of the name (word-boundary regex).
- If occurrences == 1 (only the import), remove the name from the import line.
- If the import line becomes empty, remove the entire line.
- Log actions to scripts/auto_fix_f401.log

This script is intentionally conservative to avoid breaking code.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"e:/gitcas/FlowSlide")
LOG_PATH = ROOT / "scripts" / "auto_fix_f401.log"

def run_flake8():
    p = subprocess.run([sys.executable, "-m", "flake8", "--select=F401", str(ROOT / "src")], capture_output=True, text=True)
    return p.stdout + "\n" + p.stderr

def parse_flake_output(output):
    # Expected lines like: src/flowslide/api/flowslide_api.py:15:1: F401 '.models.SlideContent' imported but unused
    entries = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"(?P<path>[^:]+):(?P<line>\d+):\d+: F401 '(?P<name>[^']+)' imported but unused", line)
        if m:
            entries.append((m.group('path').replace('/', '\\'), m.group('name')))
    return entries

WORD_RE_CACHE = {}

def count_occurrences(name):
    # simple word-boundary search across .py files in src and scripts
    pattern = re.compile(r"\\b" + re.escape(name.split('.')[-1]) + r"\\b")
    total = 0
    for p in ROOT.rglob('*.py'):
        try:
            txt = p.read_text(encoding='utf-8')
        except Exception:
            continue
        # ignore the import line itself by counting all occurrences
        if pattern.search(txt):
            total += len(pattern.findall(txt))
    return total


def remove_name_from_import(file_path, name):
    p = ROOT / file_path
    text = p.read_text(encoding='utf-8')
    lines = text.splitlines()
    changed = False
    name_simple = name.split('.')[-1]
    import_line_idx = None
    # find the import line that contains the name (first match)
    for i, line in enumerate(lines):
        if name_simple in line and ('import ' in line or 'from ' in line):
            import_line_idx = i
            break
    if import_line_idx is None:
        return False, 'import line not found'

    line = lines[import_line_idx]
    # handle both "from x import a, b" and "import a, b"
    if 'from ' in line and ' import ' in line:
        before, after = line.split(' import ', 1)
        parts = [p.strip() for p in after.split(',')]
        new_parts = [p for p in parts if p != name_simple]
        if len(new_parts) == len(parts):
            return False, 'name not in import list'
        if new_parts:
            lines[import_line_idx] = before + ' import ' + ', '.join(new_parts)
        else:
            # remove the whole line
            lines.pop(import_line_idx)
        changed = True
    elif line.strip().startswith('import '):
        after = line.split('import ', 1)[1]
        parts = [p.strip() for p in after.split(',')]
        new_parts = [p for p in parts if p != name_simple]
        if len(new_parts) == len(parts):
            return False, 'name not in import list'
        if new_parts:
            lines[import_line_idx] = 'import ' + ', '.join(new_parts)
        else:
            lines.pop(import_line_idx)
        changed = True
    else:
        return False, 'unhandled import format'

    if changed:
        p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        return True, 'modified'
    return False, 'no change'


def main():
    out = run_flake8()
    with LOG_PATH.open('w', encoding='utf-8') as logf:
        logf.write('flake8 output:\n')
        logf.write(out + '\n')

    entries = parse_flake_output(out)
    with LOG_PATH.open('a', encoding='utf-8') as logf:
        if not entries:
            logf.write('No F401 entries found.\n')
            print('No F401 entries found.')
            return
        logf.write(f'Found {len(entries)} F401 entries.\n')

        for path, name in entries:
            # count occurrences of the simple name across repo
            name_simple = name.split('.')[-1]
            occ = count_occurrences(name_simple)
            logf.write(f"Processing {path} -> {name} (simple: {name_simple}), occurrences in repo: {occ}\n")
            print(f"Processing {path} -> {name} ({occ} occurrences)")
            if occ <= 1:
                ok, msg = remove_name_from_import(path, name)
                logf.write(f"Attempted removal: {ok}, {msg}\n")
                print(f"Attempted removal: {ok}, {msg}")
            else:
                logf.write(f"Skipping {name} because it occurs {occ} times (>1).\n")
                print(f"Skipping {name} because it occurs {occ} times")

if __name__ == '__main__':
    main()
