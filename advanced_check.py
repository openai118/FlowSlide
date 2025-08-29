with open('src/flowslide/web/templates/ai_config.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# JavaScript代码从第2289行开始
js_lines = lines[2288:6256]  # 0-indexed
js_code = ''.join(js_lines)

# 检查是否有未闭合的字符串或注释
in_string = False
string_char = None
in_comment = False
comment_type = None

i = 0
while i < len(js_code):
    char = js_code[i]
    
    if in_comment:
        if comment_type == 'line' and char == '\n':
            in_comment = False
            comment_type = None
        elif comment_type == 'block' and i + 1 < len(js_code) and js_code[i:i+2] == '*/':
            in_comment = False
            comment_type = None
            i += 1  # 跳过*/
    elif in_string:
        if char == string_char:
            in_string = False
            string_char = None
        elif char == '\\' and i + 1 < len(js_code):
            i += 1  # 跳过转义字符
    else:
        if i + 1 < len(js_code) and js_code[i:i+2] == '//':
            in_comment = True
            comment_type = 'line'
            i += 1  # 跳过//
        elif i + 1 < len(js_code) and js_code[i:i+2] == '/*':
            in_comment = True
            comment_type = 'block'
            i += 1  # 跳过/*
        elif char in ('"', "'"):
            in_string = True
            string_char = char
    
    i += 1

print(f'Final state - in_string: {in_string}, in_comment: {in_comment}')
if in_string:
    print(f'Unclosed string starting with: {string_char}')
if in_comment:
    print(f'Unclosed comment of type: {comment_type}')

# 现在再次检查括号，但忽略注释和字符串中的括号
paren_stack = []
brace_stack = []

i = 0
while i < len(js_code):
    char = js_code[i]
    
    # 检查是否在注释或字符串中
    temp_i = i
    temp_in_string = False
    temp_string_char = None
    temp_in_comment = False
    temp_comment_type = None
    
    # 从头开始检查当前位置的状态
    j = 0
    while j <= i:
        t_char = js_code[j]
        
        if temp_in_comment:
            if temp_comment_type == 'line' and t_char == '\n':
                temp_in_comment = False
                temp_comment_type = None
            elif temp_comment_type == 'block' and j + 1 < len(js_code) and js_code[j:j+2] == '*/':
                temp_in_comment = False
                temp_comment_type = None
                j += 1
        elif temp_in_string:
            if t_char == temp_string_char:
                temp_in_string = False
                temp_string_char = None
            elif t_char == '\\' and j + 1 < len(js_code):
                j += 1
        else:
            if j + 1 < len(js_code) and js_code[j:j+2] == '//':
                temp_in_comment = True
                temp_comment_type = 'line'
                j += 1
            elif j + 1 < len(js_code) and js_code[j:j+2] == '/*':
                temp_in_comment = True
                temp_comment_type = 'block'
                j += 1
            elif t_char in ('"', "'"):
                temp_in_string = True
                temp_string_char = t_char
        
        j += 1
    
    # 如果不在注释或字符串中，处理括号
    if not temp_in_comment and not temp_in_string:
        if char == '(':
            paren_stack.append(i)
        elif char == ')':
            if paren_stack:
                paren_stack.pop()
            else:
                print(f'Extra closing parenthesis at position {i}')
                print(f'Context: {repr(js_code[max(0, i-30):i+30])}')
                break
        elif char == '{':
            brace_stack.append(i)
        elif char == '}':
            if brace_stack:
                brace_stack.pop()
            else:
                print(f'Extra closing brace at position {i}')
                break
    
    i += 1

print(f'Final paren stack: {len(paren_stack)} items')
print(f'Final brace stack: {len(brace_stack)} items')

if paren_stack:
    print(f'Unmatched opening parentheses at: {paren_stack[-3:]}')
if brace_stack:
    print(f'Unmatched opening braces at: {brace_stack[-3:]}')
