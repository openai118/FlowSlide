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
    script_content_end = content.find('</script>', script_content_start)

    # 计算第31880个字符在原始文件中的位置
    char_31880_in_js = 31880
    char_31880_in_file = script_content_start + char_31880_in_js

    # 计算行号
    lines = content[:char_31880_in_file].split('\n')
    line_number = len(lines)

    print(f'Character 31880 is at line {line_number}')
    print(f'Context around that position:')
    start_line = max(0, line_number - 3)
    end_line = min(len(content.split('\n')), line_number + 3)
    for i in range(start_line, end_line):
        marker = ' <-- HERE' if i == line_number - 1 else ''
        print(f'{i+1:4d}: {content.split(chr(10))[i]}{marker}')

    # 同样检查第128876个字符
    char_128876_in_js = 128876
    char_128876_in_file = script_content_start + char_128876_in_js

    lines_128876 = content[:char_128876_in_file].split('\n')
    line_number_128876 = len(lines_128876)

    print(f'\nCharacter 128876 is at line {line_number_128876}')
    print(f'Context around that position:')
    start_line_128876 = max(0, line_number_128876 - 3)
    end_line_128876 = min(len(content.split('\n')), line_number_128876 + 3)
    for i in range(start_line_128876, end_line_128876):
        marker = ' <-- HERE' if i == line_number_128876 - 1 else ''
        print(f'{i+1:4d}: {content.split(chr(10))[i]}{marker}')
