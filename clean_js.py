import re

with open('src/flowslide/web/templates/ai_config.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

js_lines = lines[2288:6256]
js_code = ''.join(js_lines)

# 替换Jinja2模板表达式
js_code = re.sub(r'{{.*?}}', '"TEMPLATE_PLACEHOLDER"', js_code)

# 保存到文件
with open('clean_js.js', 'w', encoding='utf-8') as f:
    f.write(js_code)

print("Clean JavaScript saved to clean_js.js")
print(f"Length: {len(js_code)} characters")
