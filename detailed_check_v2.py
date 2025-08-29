import re

with open('src/flowslide/web/templates/ai_config.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取JavaScript代码 - 使用与之前完全相同的逻辑
js_match = re.search(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
if js_match:
    js_code = js_match.group(1)

    print(f"Total JS characters: {len(js_code)}")

    # 检查括号匹配
    open_braces = js_code.count('{')
    close_braces = js_code.count('}')
    open_parens = js_code.count('(')
    close_parens = js_code.count(')')

    print(f'Braces: {open_braces} open, {close_braces} close')
    print(f'Parentheses: {open_parens} open, {close_parens} close')

    if open_braces != close_braces:
        print('BRACE MISMATCH!')
    if open_parens != close_parens:
        print('PARENTHESIS MISMATCH!')
        # 找到第一个不匹配的括号
        paren_stack = []
        for i, char in enumerate(js_code):
            if char == '(':
                paren_stack.append(i)
            elif char == ')':
                if paren_stack:
                    paren_stack.pop()
                else:
                    print(f'Extra closing parenthesis at position {i}')
                    print(f'Character: {repr(char)}')
                    # 显示上下文
                    start = max(0, i - 20)
                    end = min(len(js_code), i + 20)
                    print(f'Context: {repr(js_code[start:end])}')
                    break
