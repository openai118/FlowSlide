p = r"e:\gitcas\FlowSlide\src\flowslide\ai\providers.py"
out = r"e:\gitcas\FlowSlide\scripts\providers_long_lines.txt"
with open(p, 'r', encoding='utf-8') as f, open(out, 'w', encoding='utf-8') as o:
    for i, line in enumerate(f, start=1):
        s = line.rstrip('\n')
        if len(s) > 100:
            o.write(f"{i}: {len(s)}: {s}\n")
print(f"Wrote long lines to: {out}")
