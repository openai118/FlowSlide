path = r"e:\gitcas\FlowSlide\src\flowslide\ai\providers.py"
with open(path, 'rb') as f:
    lines = f.readlines()
start = 175
end = 205
for i in range(start-1, end):
    b = lines[i]
    s = b.decode('utf-8', errors='replace').rstrip('\n')
    visible = s.replace('\t', '[TAB]')
    print(f"{i+1:4}: {visible!r}  | bytes start: {list(b[:40])}")
