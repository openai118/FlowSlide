import os
import re
from pathlib import Path

TEMPLATES_DIR = Path('src/flowslide/web/templates')

# CSS properties that, if seen as bare `prop: value` in <script>, are highly suspicious
CSS_PROP_WORDS = [
    'position','inset','z-index','display','place-items','grid-template','backdrop-filter',
    'background','margin','padding','border','width','height','left','right','top','bottom',
    'color','font','align-items','justify-content','overflow','opacity','flex','gap','cursor'
]

PROP_REGEX = re.compile(r'(?:^|[;{\n\r])\s*(%s)\s*:\s*[^;{}]+;?' % '|'.join(map(re.escape, CSS_PROP_WORDS)), re.IGNORECASE)
SCRIPT_OPEN_RE = re.compile(r'<script[^>]*>', re.IGNORECASE)
SCRIPT_CLOSE = '</script>'


def scan_file(path: Path):
    text = path.read_text(encoding='utf-8')
    issues = []
    idx = 0
    while True:
        m = SCRIPT_OPEN_RE.search(text, idx)
        if not m:
            break
        start = m.end()
        end = text.find(SCRIPT_CLOSE, start)
        if end == -1:
            break
        block = text[start:end]
        # quick ignore heuristic: skip blocks that are clearly JSON-LD etc
        if 'application/ld+json' in m.group(0).lower():
            idx = end + len(SCRIPT_CLOSE)
            continue
        for i, line in enumerate(block.splitlines(), 1):
            # ignore obvious JS contexts
            if 'style.' in line or 'cssText' in line or 'setProperty' in line:
                continue
            if PROP_REGEX.search(line):
                # try to check if inside quotes (very rough): odd number of quotes up to this line
                upto = '\n'.join(block.splitlines()[:i])
                if (upto.count("'") % 2) or (upto.count('"') % 2):
                    # likely inside a string, skip (reduce false positives)
                    continue
                issues.append((i, line.strip()))
        idx = end + len(SCRIPT_CLOSE)
    return issues


def main():
    any_issue = False
    for p in sorted(TEMPLATES_DIR.glob('*.html')):
        issues = scan_file(p)
        if issues:
            any_issue = True
            print(f'FILE: {p}')
            for line_no, line in issues[:50]:
                print(f'  script line {line_no}: {line}')
            print('-' * 60)
    if not any_issue:
        print('✅ No suspicious CSS-like statements found inside <script> blocks.')

if __name__ == '__main__':
    main()

