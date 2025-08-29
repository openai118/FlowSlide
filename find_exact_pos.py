import re

with open('src/flowslide/web/templates/ai_config.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取JavaScript代码
js_match = re.search(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
if js_match:
    js_code = js_match.group(1)

    # 找到script标签的位置
    script_start = content.find('<script')
    script_content_start = content.find('>', script_start) + 1

    # 计算第31880个字符在文件中的位置
    file_pos = script_content_start + 31880

    print(f"JS position 31880 corresponds to file position {file_pos}")
    print(f"Character at file position {file_pos}: {repr(content[file_pos])}")

    # 显示更大上下文
    start = max(0, file_pos - 100)
    end = min(len(content), file_pos + 100)
    print(f"\nContext around file position {file_pos}:")
    print(repr(content[start:end]))

    # 显示行号
    lines = content[:file_pos].split('\n')
    line_number = len(lines)
    print(f"\nThis is at line {line_number}")

    # 显示该行的内容
    if line_number <= len(content.split('\n')):
        print(f"Line {line_number}: {repr(content.split(chr(10))[line_number-1])}")
