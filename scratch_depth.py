from pathlib import Path

content = Path('app/static/js/file-utils.js').read_text(encoding='utf-8', errors='ignore')

lines = content.split('\n')
depth = 0
in_str = None
in_comment = False

for idx, line in enumerate(lines, 1):
    i = 0
    while i < len(line):
        if in_comment:
            if line[i:i+2] == '*/':
                in_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_str:
            if line[i] == '\\':
                i += 2
                continue
            if line[i] == in_str:
                in_str = None
            i += 1
            continue
        if line[i:i+2] == '//':
            break
        if line[i:i+2] == '/*':
            in_comment = True
            i += 2
            continue
        if line[i] in ('"', "'", '`'):
            in_str = line[i]
            i += 1
            continue
        if line[i] == '{':
            depth += 1
        elif line[i] == '}':
            depth -= 1
        i += 1
    if depth == 0:
        print(f'L{idx:3d} reached Depth 0: {line.strip()[:60]}')

print(f'Final depth: {depth}')
