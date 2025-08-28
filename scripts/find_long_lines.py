import io

def find_long_lines(path, limit=100):
    with io.open(path, 'r', encoding='utf-8') as f:
        res = []
        for i, l in enumerate(f):
            if len(l.rstrip('\r\n')) > limit:
                res.append(f"{i+1}:{len(l.rstrip('\r\n'))}:{l.rstrip()}".replace('\t','    '))
    return res

if __name__ == '__main__':
    import sys
    path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else 'scripts/long_lines.txt'
    lines = find_long_lines(path)
    with io.open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'Wrote {len(lines)} long lines to {out}')
