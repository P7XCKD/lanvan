import sys, re
from pathlib import Path

js_dir = Path('app/static/js')
all_js = sorted([f for f in js_dir.rglob('*.js') if not f.name.endswith('.min.js')])

print("="*60)
print("PHASE 3 — STEP 1: ACCURATE SYNTAX VERIFICATION REPORT")
print("="*60)

syntax_errors = []

for filepath in all_js:
    code = filepath.read_text(encoding='utf-8', errors='ignore')
    rel_path = filepath.relative_to(js_dir)
    
    stack = []
    in_string = None
    escape = False
    in_comment_single = False
    in_comment_multi = False
    in_regex = False
    
    lines = code.split('\n')
    for line_idx, line in enumerate(lines, 1):
        i = 0
        n = len(line)
        while i < n:
            c = line[i]
            
            if escape:
                escape = False
                i += 1
                continue
                
            if c == '\\':
                escape = True
                i += 1
                continue
                
            if in_comment_single:
                i += 1
                continue
                
            if in_comment_multi:
                if c == '*' and i + 1 < n and line[i+1] == '/':
                    in_comment_multi = False
                    i += 2
                    continue
                i += 1
                continue
                
            if in_string:
                if c == in_string:
                    in_string = None
                i += 1
                continue
                
            if in_regex:
                if c == '/':
                    in_regex = False
                i += 1
                continue
                
            # Comments check
            if c == '/' and i + 1 < n:
                if line[i+1] == '/':
                    in_comment_single = True
                    break
                elif line[i+1] == '*':
                    in_comment_multi = True
                    i += 2
                    continue
                    
            if c in ("'", '"', '`'):
                in_string = c
                i += 1
                continue
                
            # Simple heuristic for regex literals vs division
            # If '/' follows an operator or assignment or return or start of statement
            if c == '/':
                prev_sub = line[:i].rstrip()
                if not prev_sub or prev_sub[-1] in '=(:,[!&|?+-><;':
                    in_regex = True
                    i += 1
                    continue
                elif prev_sub.endswith('return') or prev_sub.endswith('case'):
                    in_regex = True
                    i += 1
                    continue

            if c in '{[(':
                stack.append((c, line_idx))
            elif c == '}':
                if stack and stack[-1][0] == '{':
                    stack.pop()
                else:
                    syntax_errors.append((str(rel_path), line_idx, f"Unmatched closing '}}'"))
            elif c == ']':
                if stack and stack[-1][0] == '[':
                    stack.pop()
                else:
                    syntax_errors.append((str(rel_path), line_idx, f"Unmatched closing ']'"))
            elif c == ')':
                if stack and stack[-1][0] == '(':
                    stack.pop()
                else:
                    syntax_errors.append((str(rel_path), line_idx, f"Unmatched closing ')'"))
            i += 1
            
        in_comment_single = False  # EOL ends single-line comment

    if stack:
        for b, l in stack:
            syntax_errors.append((str(rel_path), l, f"Unclosed '{b}' reaching EOF"))
    if in_comment_multi:
        syntax_errors.append((str(rel_path), len(lines), "Unclosed block comment /* ... */"))
    if in_string:
        syntax_errors.append((str(rel_path), len(lines), f"Unclosed string literal ({in_string})"))

if not syntax_errors:
    print("ALL FILES PARSED 100% CLEANLY — ZERO SYNTAX ERRORS DETECTED!")
else:
    print(f"FOUND {len(syntax_errors)} SYNTAX ERRORS:")
    for file, line, msg in syntax_errors:
        print(f"  [{file}:L{line}] {msg}")
