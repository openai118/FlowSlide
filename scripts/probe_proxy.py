#!/usr/bin/env python3
"""Simple probe script for upstream proxy.

Usage:
    - Set API key via environment variable API_KEY, or pass as first CLI arg.
        Example (PowerShell): $env:API_KEY='1144'; python scripts\\probe_proxy.py

This script will NOT hardcode API keys into repository files.
"""
import os
import sys
import urllib.request
import urllib.error
import json

URL_BASE = 'https://aiload.i2you.me/proxy/newapi/v1'


def get_api_key():
    # CLI arg first, then environment variable
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    return os.environ.get('API_KEY')


def do_get_models(api_key=None):
    url = f"{URL_BASE}/models"
    print('GET', url)
    req = urllib.request.Request(url, method='GET')
    if api_key:
        # Forward both common auth headers to cover proxy variations
        req.add_header('Authorization', f'Bearer {api_key}')
        req.add_header('X-Api-Key', api_key)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = getattr(resp, 'status', None)
            body = resp.read().decode('utf-8', errors='replace')
            print('STATUS', status)
            print('BODY', body[:2000])
    except urllib.error.HTTPError as he:
        try:
            body = he.read().decode('utf-8', errors='replace')
        except Exception:
            body = str(he)
        print('HTTP ERROR', he.code)
        print('BODY', body[:2000])
    except Exception as e:
        print('ERROR', e)


def do_post_chat(api_key=None):
    url = f"{URL_BASE}/api/chat"
    print('\nPOST', url)
    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello"}]
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Content-Type', 'application/json')
    if api_key:
        req.add_header('Authorization', f'Bearer {api_key}')
        req.add_header('X-Api-Key', api_key)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = getattr(resp, 'status', None)
            body = resp.read().decode('utf-8', errors='replace')
            print('STATUS', status)
            print('BODY', body[:2000])
    except urllib.error.HTTPError as he:
        try:
            body = he.read().decode('utf-8', errors='replace')
        except Exception:
            body = str(he)
        print('HTTP ERROR', he.code)
        print('BODY', body[:2000])
    except Exception as e:
        print('ERROR', e)


if __name__ == '__main__':
    key = get_api_key()
    if key:
        print('Using API key from env/arg (masked):', key[:2] + '***')
    else:
        print('No API key provided; testing unauthenticated')
    do_get_models(api_key=key)
    do_post_chat(api_key=key)
