p = r"e:\gitcas\FlowSlide\src\flowslide\ai\providers.py"
out = r"e:\gitcas\FlowSlide\scripts\providers_lines.txt"
with open(p,'r',encoding='utf-8') as f, open(out,'w',encoding='utf-8') as o:
    for i,line in enumerate(f, start=1):
        o.write(f"{i:4}: {line.rstrip('\n')[:1000]}\n")
print('wrote', out)
