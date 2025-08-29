import re

with open('src/flowslide/web/templates/ai_config.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取JavaScript代码
js_match = re.search(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
if js_match:
    js_code = js_match.group(1)
    print(f'Total JS characters: {len(js_code)}')

    # 检查括号匹配
    open_braces = js_code.count('{')
    close_braces = js_code.count('}')
    open_parens = js_code.count('(')
    close_parens = js_code.count(')')

    print(f'Braces: {open_braces} open, {close_braces} close')
    print(f'Parentheses: {open_parens} open, {close_parens} close')

    if open_braces != close_braces:
        print('BRACE MISMATCH!')
        # 找到最后一个未匹配的括号
        brace_stack = []
        for i, char in enumerate(js_code):
            if char == '{':
                brace_stack.append(i)
            elif char == '}':
                if brace_stack:
                    brace_stack.pop()
                else:
                    print(f'Extra closing brace at position {i}')
                    break
        if brace_stack:
            print(f'Unmatched opening brace at position {brace_stack[-1]}')

    if open_parens != close_parens:
        print('PARENTHESIS MISMATCH!')
        # 找到最后一个未匹配的括号
        paren_stack = []
        for i, char in enumerate(js_code):
            if char == '(':
                paren_stack.append(i)
            elif char == ')':
                if paren_stack:
                    paren_stack.pop()
                else:
                    print(f'Extra closing parenthesis at position {i}')
                    break
        if paren_stack:
            print(f'Unmatched opening parenthesis at position {paren_stack[-1]}')
