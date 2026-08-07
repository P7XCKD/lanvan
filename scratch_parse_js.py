from pathlib import Path

code = Path('app/static/js/file-utils.js').read_text(encoding='utf-8', errors='ignore')

stack = []
in_string = None
escape = False
in_comment_single = False
in_comment_multi = False

i = 0
n = len(code)

while i < n:
    c = code[i]
    
    if in_comment_single:
        if c == '\n':
            in_comment_single = False
        i += 1
        continue
        
    if in_comment_multi:
        if c == '*' and i + 1 < n and code[i+1] == '/':
            in_comment_multi = False
            i += 2
            continue
        i += 1
        continue
        
    if in_string:
        if escape:
            escape = False
        elif c == '\\':
            escape = True
        elif c == in_string:
            in_string = None
        i += 1
        continue
        
    # Check comments
    if c == '/' and i + 1 < n:
        if code[i+1] == '/':
            in_comment_single = True
            i += 2
            continue
        elif code[i+1] == '*':
            in_comment_multi = True
            i += 2
            continue
            
    if c in ("'", '"', '`'):
        in_string = c
        i += 1
        continue
        
    line_no = code[:i].count('\n') + 1
    
    if c in '{[(':
        stack.append((c, line_no))
    elif c == '}':
        if not stack or stack[-1][0] != '{':
            print(f'Unmatched closing }} at line {line_no}')
        else:
            stack.pop()
    elif c == ']':
        if not stack or stack[-1][0] != '[':
            print(f'Unmatched closing ] at line {line_no}')
        else:
            stack.pop()
    elif c == ')':
        if not stack or stack[-1][0] != '(':
            print(f'Unmatched closing ) at line {line_no}')
        else:
            stack.pop()
            
    i += 1

print('Done parsing.')
if stack:
    print(f'Unclosed count: {len(stack)}')
    for b, l in stack:
        print(f'  Unclosed {b} from line {l}')
else:
    print('100% PERFECT BALANCE!')
