#!/usr/bin/env python3
"""POST to /v1/chat/completions and save decoded response (errors replaced) to a file.

Use API key from CLI arg or API_KEY env var.
"""
import os
import sys
import urllib.request
import urllib.error
import json

URL_BASE = 'https://aiload.i2you.me/proxy/newapi/v1'
OUT_FILE = os.path.join('scripts', 'probe_chat_response.txt')


def get_api_key():
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    return os.environ.get('API_KEY')


def do_post_chat(api_key=None):
    url = f"{URL_BASE}/chat/completions"
    print('DEBUG: url=', url)
    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello"}]
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Content-Type', 'application/json')
    if api_key:
        req.add_header('Authorization', f'Bearer {api_key}')
        req.add_header('X-Api-Key', api_key)
    print('DEBUG: headers=', {k: ('***' if 'api' in k.lower() else v) for k, v in req.header_items()})
    print('DEBUG: payload_bytes=', len(payload))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, 'status', None)
            body_bytes = resp.read()
            body_text = body_bytes.decode('utf-8', errors='replace')
            with open(OUT_FILE, 'w', encoding='utf-8') as fh:
                fh.write(f'STATUS {status}\n')
                fh.write(body_text)
            print('Saved response to', OUT_FILE)
    except urllib.error.HTTPError as he:
        try:
            body = he.read().decode('utf-8', errors='replace')
        except Exception:
            body = str(he)
        with open(OUT_FILE, 'w', encoding='utf-8') as fh:
            fh.write(f'HTTP ERROR {he.code}\n')
            fh.write(body)
        print('Saved HTTP error to', OUT_FILE)
    except Exception as e:
        with open(OUT_FILE, 'w', encoding='utf-8') as fh:
            fh.write('EXCEPTION\n')
            fh.write(repr(e))
        print('Saved exception to', OUT_FILE)


if __name__ == '__main__':
    key = get_api_key()
    if key:
        print('Using API key (masked):', key[:2] + '***')
    else:
        print('No API key provided')
    do_post_chat(api_key=key)
