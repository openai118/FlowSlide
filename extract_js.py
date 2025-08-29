import re

with open('src/flowslide/web/templates/ai_config.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取JavaScript代码
js_match = re.search(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
if js_match:
    js_code = js_match.group(1)

    # 保存到临时文件进行语法检查
    with open('temp_js.js', 'w', encoding='utf-8') as f:
        f.write(js_code)

    print("JavaScript code extracted and saved to temp_js.js")
    print(f"Total characters: {len(js_code)}")

    # 简单的括号检查
    parens = 0
    braces = 0
    for char in js_code:
        if char == '(':
            parens += 1
        elif char == ')':
            parens -= 1
        elif char == '{':
            braces += 1
        elif char == '}':
            braces -= 1

    print(f"Final parenthesis balance: {parens}")
    print(f"Final brace balance: {braces}")

    if parens == 0 and braces == 0:
        print("Basic syntax check passed!")
    else:
        print("Syntax issues detected!")
