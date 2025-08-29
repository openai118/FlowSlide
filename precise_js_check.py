with open('src/flowslide/web/templates/ai_config.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 提取JavaScript代码（从第2289行到第6256行）
js_lines = lines[2288:6256]  # 0-indexed, so line 2289 is at index 2288
js_code = ''.join(js_lines)

print(f"JavaScript code length: {len(js_code)} characters")
print(f"Number of JS lines: {len(js_lines)}")

# 检查括号
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
    # 找到不匹配的括号
    paren_stack = []
    for i, char in enumerate(js_code):
        if char == '(':
            paren_stack.append(i)
        elif char == ')':
            if paren_stack:
                paren_stack.pop()
            else:
                print(f'Extra closing parenthesis at position {i}')
                # 显示上下文
                start = max(0, i - 50)
                end = min(len(js_code), i + 50)
                print(f'Context: {repr(js_code[start:end])}')
                break

    if paren_stack:
        print(f'Unmatched opening parentheses at positions: {paren_stack[-5:]}')  # 显示最后5个
