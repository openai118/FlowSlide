p = r"e:\gitcas\FlowSlide\src\flowslide\ai\providers.py"
with open(p, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, start=1):
        s = line.rstrip('\n')
        if len(s) > 100 or 'max_tokens' in s:
            print(f"{i}: {len(s)}: {s}")
