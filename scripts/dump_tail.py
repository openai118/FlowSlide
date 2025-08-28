import io,sys
p='src/flowslide/api/config_api.py'
with io.open(p,'r',encoding='utf-8') as f:
    lines=f.readlines()
for i,l in enumerate(lines[-12:], start=len(lines)-11):
    print(f"{i}: {repr(l)}")
