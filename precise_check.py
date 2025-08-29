import re

with open('src/flowslide/web/templates/ai_config.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取JavaScript代码
js_match = re.search(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
if js_match:
    js_code = js_match.group(1)

    # 找到第31880个字符在原始文件中的位置
    script_start = content.find('<script')
    script_content_start = content.find('>', script_start) + 1

    # 计算第31880个字符在原始文件中的位置
    char_31880_in_file = script_content_start + 31880

    # 获取该位置的上下文
    context_start = max(0, char_31880_in_file - 50)
    context_end = min(len(content), char_31880_in_file + 50)

    print(f'Character at position 31880 in JS:')
    print(repr(content[char_31880_in_file]))

    print(f'\nContext around position {char_31880_in_file}:')
    print(repr(content[context_start:context_end]))

    # 检查括号平衡
    paren_stack = []
    for i, char in enumerate(js_code):
        if char == '(':
            paren_stack.append(i)
        elif char == ')':
            if paren_stack:
                paren_stack.pop()
            else:
                print(f'\nExtra closing parenthesis at JS position {i}')
                # 找到对应的文件位置
                file_pos = script_content_start + i
                print(f'File position: {file_pos}')
                # 显示上下文
                ctx_start = max(0, file_pos - 100)
                ctx_end = min(len(content), file_pos + 100)
                print('Context:')
                print(repr(content[ctx_start:ctx_end]))
                break

    if paren_stack:
        print(f'\nUnmatched opening parentheses at positions: {paren_stack}')
        for pos in paren_stack[-3:]:  # 显示最后3个
            file_pos = script_content_start + pos
            print(f'  JS pos {pos} -> File pos {file_pos}: {repr(content[file_pos])}')
            ctx_start = max(0, file_pos - 50)
            ctx_end = min(len(content), file_pos + 50)
            print(f'    Context: {repr(content[ctx_start:ctx_end])}')
