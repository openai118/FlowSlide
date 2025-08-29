import re

with open('src/flowslide/web/templates/ai_config.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 检查JavaScript语法错误
js_blocks = re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
for i, js in enumerate(js_blocks):
    print(f'JavaScript block {i+1}: {len(js)} characters')
    # 检查基本语法
    if js.count('{') != js.count('}'):
        print(f'  Block {i+1}: Unmatched braces - {js.count("{")} open, {js.count("}")} close')
    if js.count('(') != js.count(')'):
        print(f'  Block {i+1}: Unmatched parentheses - {js.count("(")} open, {js.count(")")} close')
