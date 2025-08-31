from pathlib import Path
import re, json

s = Path('ai_config_api_logged.html').read_text(encoding='utf-8')
start = s.find('<div id="data-backup"')
if start == -1:
    print(json.dumps({'found': False}, ensure_ascii=False))
    raise SystemExit(0)

open_end = s.find('>', start)
if open_end == -1:
    print(json.dumps({'found': False, 'error': 'no_end'}, ensure_ascii=False))
    raise SystemExit(0)

idx = open_end + 1
count = 1
end_idx = None
while idx < len(s):
    m_open = s.find('<div', idx)
    m_close = s.find('</div>', idx)
    if m_close == -1:
        break
    if m_open != -1 and m_open < m_close:
        count += 1
        idx = m_open + 4
    else:
        count -= 1
        idx = m_close + 6
    if count == 0:
        end_idx = idx
        break

if end_idx is None:
    print(json.dumps({'found': False, 'error': 'no_matching_close'}, ensure_ascii=False))
    raise SystemExit(0)

sub = s[start:end_idx]
text = re.sub(r'<[^>]+>', '', sub).strip()

res = {
    'found': True,
    'text_len': len(text),
    'direct_children_estimate': len(re.findall(r'<\s*([a-zA-Z0-9]+)([^>]*)>', sub)) - 1,
    'has_display_none': bool(re.search(r'style\s*=\s*"[^"]*display\s*:\s*none', sub)),
    'has_pos_abs': bool(re.search(r'position\s*:\s*absolute', sub, flags=re.I)),
    'abs_count': len(re.findall(r'position\s*:\s*absolute', sub, flags=re.I)),
    'first_300': sub[:300]
}

print(json.dumps(res, ensure_ascii=False, indent=2))
