import re
from pathlib import Path
import json

def find_element_substring(html, id_name):
    # find the opening tag with id
    m = re.search(r'<([a-zA-Z0-9]+)([^>]*\bid\s*=\s*["\']%s["\'])' % re.escape(id_name), html)
    if not m:
        return None
    start_tag_start = m.start()
    # find the end of the start tag
    start_tag_end = html.find('>', start_tag_start)
    if start_tag_end == -1:
        return None
    i = start_tag_end + 1
    depth = 1
    # scan forward counting opening and closing tags of same type? We'll count general tags < and </
    while i < len(html):
        next_open = html.find('<', i)
        if next_open == -1:
            break
        # check if it's a closing tag
        if html.startswith('</', next_open):
            depth -= 1
            i = html.find('>', next_open)
            if i == -1:
                break
            i += 1
            if depth == 0:
                return html[start_tag_start:i]
        else:
            # opening tag - self-closing tags with '/' before '>' still count as opening then immediate close
            # To be conservative, increment depth for any '<' that's not a comment or doctype
            if not html.startswith('<!--', next_open) and not html.startswith('<!', next_open) and not html.startswith('<?', next_open):
                depth += 1
            i = html.find('>', next_open)
            if i == -1:
                break
            i += 1
    return None


def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s)

html = Path('ai_config_api_logged.html').read_text(encoding='utf-8')
sub = find_element_substring(html, 'data-backup')
if sub is None:
    print(json.dumps({'found': False}, ensure_ascii=False))
    raise SystemExit(0)

# compute text length
text = strip_tags(sub).strip()
text_len = len(text)

# compute direct child opening tags at depth 1
# we scan the substring, track depth: start after the first '>'
start = sub.find('>') + 1
depth = 0
direct_children = 0
i = start
while i < len(sub):
    idx = sub.find('<', i)
    if idx == -1:
        break
    # skip comments
    if sub.startswith('<!--', idx):
        endc = sub.find('-->', idx)
        if endc == -1:
            break
        i = endc + 3
        continue
    # closing tag
    if sub.startswith('</', idx):
        depth -= 1
        i = sub.find('>', idx)
        if i == -1:
            break
        i += 1
        continue
    # opening tag
    # ignore doctype
    if sub.startswith('<!', idx) or sub.startswith('<?', idx):
        i = sub.find('>', idx)
        if i == -1:
            break
        i += 1
        continue
    # it's an opening tag
    # if current depth==0 then this is a direct child
    if depth == 0:
        direct_children += 1
    depth += 1
    i = sub.find('>', idx)
    if i == -1:
        break
    i += 1

# detect inline styles that could collapse layout
has_pos_abs = bool(re.search(r'position\s*:\s*absolute', sub, flags=re.I))
has_display_none = bool(re.search(r'display\s*:\s*none', sub, flags=re.I))
# detect any child with style containing height:0 or overflow:hidden maybe
has_height_zero = bool(re.search(r'height\s*:\s*0', sub, flags=re.I))

# also detect if many elements are absolutely positioned inside by checking patterns like "position:absolute" on child tags
abs_count = len(re.findall(r'position\s*:\s*absolute', sub, flags=re.I))

res = {
    'found': True,
    'text_len': text_len,
    'direct_children': direct_children,
    'has_pos_abs': has_pos_abs,
    'has_display_none': has_display_none,
    'has_height_zero': has_height_zero,
    'abs_count': abs_count,
}
print(json.dumps(res, ensure_ascii=False, indent=2))
