with open('src/flowslide/web/templates/ai_config.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# JavaScript代码从第2289行开始（0-indexed为2288）
js_start_line = 2288
js_lines = lines[js_start_line:6256]  # 到第6256行（包含）
js_code = ''.join(js_lines)

# 找到第31888个字符
char_pos = 31888
if char_pos < len(js_code):
    print(f"Character at JS position {char_pos}: {repr(js_code[char_pos])}")
    
    # 计算这个字符在哪一行
    line_start = 0
    for line_num, line in enumerate(js_lines):
        line_end = line_start + len(line)
        if line_start <= char_pos < line_end:
            char_in_line = char_pos - line_start
            print(f"This is at JS line {line_num + 1} (file line {js_start_line + line_num + 1}), character {char_in_line}")
            print(f"Line content: {repr(line)}")
            print(f"Character at position {char_in_line}: {repr(line[char_in_line])}")
            break
        line_start = line_end
else:
    print(f"Position {char_pos} is beyond JS code length ({len(js_code)})")
