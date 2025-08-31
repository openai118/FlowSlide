from bs4 import BeautifulSoup
p='f:/projects/FlowSlide/ai_config_api_logged.html'
html=open(p,'r',encoding='utf-8').read()
soup=BeautifulSoup(html,'html.parser')
d=soup.select_one('#data-backup')
print('found', bool(d))
print('inline style:', d.get('style') if d else '')
# count elements with inline display:none inside
none_count=len([e for e in d.select('*') if e.get('style') and 'display:none' in e.get('style').replace(' ', '')])
print('inline display:none count:', none_count)
# print first 12 descendant tags and their inline style
if d:
  for i,ch in enumerate(d.find_all(recursive=True)[:12]):
    print(i, ch.name, ch.get('class'), ch.get('style'))
