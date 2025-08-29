with open('src/flowslide/web/templates/ai_config.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

js_lines = lines[2288:6256]
js_code = ''.join(js_lines)

# 检查反引号匹配
backtick_count = js_code.count('`')
print(f'Total backticks: {backtick_count}')

if backtick_count % 2 != 0:
    print('UNMATCHED BACKTICKS!')
    
    # 找到最后一个反引号
    last_backtick = js_code.rfind('`')
    print(f'Last backtick at position {last_backtick}')
    
    # 显示上下文
    start = max(0, last_backtick - 100)
    end = min(len(js_code), last_backtick + 100)
    print(f'Context around last backtick:')
    print(repr(js_code[start:end]))
else:
    print('Backticks are properly matched')
