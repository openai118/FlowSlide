import re

with open('src/flowslide/web/templates/ai_config.html', 'rb') as f:
    content = f.read()

# 找到script标签
script_start = content.find(b'<script')
script_end = content.find(b'</script>', script_start) + len(b'</script>')

# 提取JavaScript部分
js_content = content[script_start:script_end]

# 找到第31880个字符在JS内容中的位置
script_tag_end = js_content.find(b'>') + 1
js_code_start = script_tag_end
js_code = js_content[js_code_start:-len(b'</script>')]

print(f"JS code length: {len(js_code)}")
print(f"Looking for position 31880")

if 31880 < len(js_code):
    char = js_code[31880]
    print(f"Character at position 31880: {repr(chr(char))}")
    print(f"Hex value: 0x{char:02x}")

    # 显示上下文
    start = max(0, 31880 - 10)
    end = min(len(js_code), 31880 + 10)
    context = js_code[start:end]
    print(f"Context bytes: {[hex(b) for b in context]}")
    print(f"Context chars: {repr(context.decode('utf-8', errors='replace'))}")
else:
    print(f"Position 31880 is beyond JS code length ({len(js_code)})")
