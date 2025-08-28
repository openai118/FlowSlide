import io
p='src/flowslide/api/config_api.py'
with io.open(p,'r',encoding='utf-8') as f:
    s=f.read()
# strip trailing whitespace/newlines
s = s.rstrip('\r\n') + '\n'
with io.open(p,'w',encoding='utf-8') as f:
    f.write(s)
print('normalized',p)
