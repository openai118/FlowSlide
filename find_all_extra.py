with open('src/flowslide/web/templates/ai_config.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

js_lines = lines[2288:6256]
js_code = ''.join(js_lines)

# 找到所有多余的闭合括号
paren_stack = []
extra_closes = []

for i, char in enumerate(js_code):
    if char == '(':
        paren_stack.append(i)
    elif char == ')':
        if paren_stack:
            paren_stack.pop()
        else:
            extra_closes.append(i)

print(f'Found {len(extra_closes)} extra closing parentheses')
for i, pos in enumerate(extra_closes):
    print(f'{i+1}. Position {pos}:')
    # 显示上下文
    start = max(0, pos - 40)
    end = min(len(js_code), pos + 40)
    context = js_code[start:end]
    print(f'   Context: {repr(context)}')
    
    # 计算行号
    line_num = sum(1 for _ in js_code[:pos].split('\n'))
    print(f'   At JS line {line_num} (file line {2289 + line_num - 1})')
    print()
