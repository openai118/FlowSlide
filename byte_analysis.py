import re

with open('src/flowslide/web/templates/ai_config.html', 'rb') as f:
    content = f.read()

# 找到script标签
script_start = content.find(b'<script')
script_content_start = content.find(b'>', script_start) + 1
script_content_end = content.find(b'</script>', script_content_start)

# 计算第31880个字符在文件中的位置
file_pos = script_content_start + 31880

print(f"Script content starts at byte {script_content_start}")
print(f"Looking for JS position 31880 -> File position {file_pos}")

# 显示该位置的上下文
start = max(0, file_pos - 50)
end = min(len(content), file_pos + 50)

print(f"Context around file position {file_pos}:")
for i in range(start, end):
    if i == file_pos:
        print(f"[{i:6d}] -> {content[i]:3d} 0x{content[i]:02x} '{chr(content[i]) if 32 <= content[i] <= 126 else '?'}'  <-- TARGET")
    else:
        print(f" {i:6d}    {content[i]:3d} 0x{content[i]:02x} '{chr(content[i]) if 32 <= content[i] <= 126 else '?'}'")

# 检查是否有任何异常字符
target_char = content[file_pos]
print(f"\nTarget character analysis:")
print(f"  Decimal: {target_char}")
print(f"  Hex: 0x{target_char:02x}")
print(f"  Char: '{chr(target_char) if 32 <= target_char <= 126 else 'NON-PRINTABLE'}'")
print(f"  Is closing paren: {target_char == ord(')')}")
