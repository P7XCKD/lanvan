from pathlib import Path

for f in sorted(Path('app/static/js').rglob('*.js')):
    if f.name in ('docx-preview.min.js', 'jszip.min.js', 'lucide.min.js'):
        continue
    code = f.read_text(encoding='utf-8', errors='ignore')
    stack = []
    in_string = None
    escape = False
    in_comment_single = False
    in_comment_multi = False
    regex_charclass = False
    
    i = 0
    n = len(code)
    while i < n:
        c = code[i]
        
        if escape:
            escape = False
            i += 1
            continue
            
        if c == '\\':
            escape = True
            i += 1
            continue
            
        if in_comment_single:
            if c == '\n': in_comment_single = False
            i += 1; continue
        if in_comment_multi:
            if c == '*' and i + 1 < n and code[i+1] == '/': in_comment_multi = False; i += 2; continue
            i += 1; continue
        if in_string:
            if c == in_string: in_string = None
            i += 1; continue
            
        if c == '/' and i + 1 < n:
            if code[i+1] == '/': in_comment_single = True; i += 2; continue
            elif code[i+1] == '*': in_comment_multi = True; i += 2; continue
            
        if c in ("'", '"', '`'):
            in_string = c
            i += 1
            continue
            
        if c in '{[(':
            stack.append((c, code[:i].count('\n') + 1))
        elif c == '}':
            if stack and stack[-1][0] == '{': stack.pop()
            else: print(f'{f.name}: Unmatched }} at line {code[:i].count("\n") + 1}')
        elif c == ']':
            if stack and stack[-1][0] == '[': stack.pop()
            else: print(f'{f.name}: Unmatched ] at line {code[:i].count("\n") + 1}')
        elif c == ')':
            if stack and stack[-1][0] == '(': stack.pop()
            else: print(f'{f.name}: Unmatched ) at line {code[:i].count("\n") + 1}')
        i += 1
        
    if stack:
        print(f'UNCLOSED IN {f.name}: {len(stack)}')
        for b, l in stack:
            print(f'  {b} at L{l}')
    else:
        print(f'OK: {f.name}')
