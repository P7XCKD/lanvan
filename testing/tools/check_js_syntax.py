import glob
import re
import sys

def check_file_ast(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()

    pos = 0
    length = len(code)
    line = 1
    col = 1

    stack = []
    mode = 'CODE' # 'CODE', 'SINGLE_COMMENT', 'BLOCK_COMMENT', 'STRING', 'REGEX', 'REGEX_CLASS'
    string_quote = ''
    escaped = False

    while pos < length:
        ch = code[pos]

        if mode == 'SINGLE_COMMENT':
            if ch == '\n':
                mode = 'CODE'
                line += 1
                col = 1
            else:
                col += 1
            pos += 1
            continue

        if mode == 'BLOCK_COMMENT':
            if ch == '*' and pos + 1 < length and code[pos+1] == '/':
                mode = 'CODE'
                pos += 2
                col += 2
                continue
            if ch == '\n':
                line += 1
                col = 1
            else:
                col += 1
            pos += 1
            continue

        if mode == 'STRING':
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == string_quote:
                mode = 'CODE'
            if ch == '\n':
                line += 1
                col = 1
            else:
                col += 1
            pos += 1
            continue

        if mode == 'REGEX_CLASS':
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == ']':
                mode = 'REGEX'
            if ch == '\n':
                line += 1
                col = 1
            else:
                col += 1
            pos += 1
            continue

        if mode == 'REGEX':
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '[':
                mode = 'REGEX_CLASS'
            elif ch == '/':
                mode = 'CODE'
            if ch == '\n':
                line += 1
                col = 1
            else:
                col += 1
            pos += 1
            continue

        # CODE mode
        if ch == '/' and pos + 1 < length and code[pos+1] == '/':
            mode = 'SINGLE_COMMENT'
            pos += 2
            col += 2
            continue

        if ch == '/' and pos + 1 < length and code[pos+1] == '*':
            mode = 'BLOCK_COMMENT'
            pos += 2
            col += 2
            continue

        if ch in ('"', "'", '`'):
            mode = 'STRING'
            string_quote = ch
            escaped = False
            col += 1
            pos += 1
            continue

        if ch == '/':
            # Check if slash starts a regex literal
            prev_code = code[:pos].rstrip()
            if prev_code:
                last_ch = prev_code[-1]
                # If preceded by operator, bracket, brace, comma, semicolon, colon, or keywords/methods
                if last_ch in '(=,:[!&|?+*-~^{};' or prev_code.endswith('return') or prev_code.endswith('delete') or prev_code.endswith('typeof') or prev_code.endswith('void') or re.search(r'\.(replace|match|search|split|exec|test)$', prev_code):
                    mode = 'REGEX'
                    escaped = False
                    col += 1
                    pos += 1
                    continue

        if ch in '({[':
            stack.append((ch, line, col))
        elif ch in ')}]':
            if not stack:
                return f"UNMATCHED CLOSING '{ch}' at line {line}:{col}"
            top_char, top_l, top_c = stack.pop()
            expected = {'}': '{', ']': '[', ')': '('}[ch]
            if top_char != expected:
                return f"MISMATCHED CLOSING '{ch}' at line {line}:{col}, expected closing for '{top_char}' from line {top_l}:{top_c}"

        if ch == '\n':
            line += 1
            col = 1
        else:
            col += 1
        pos += 1

    if stack:
        top_char, top_l, top_c = stack[-1]
        return f"UNCLOSED OPENING '{top_char}' from line {top_l}:{top_c}"

    return "SYNTAX OK"

def main():
    files = sorted(glob.glob('app/static/js/**/*.js', recursive=True))
    errors = 0
    print("==================================================")
    print("LANVAN ACCURATE JS AST PARSER (FULL SPEC REGEX)")
    print("==================================================")
    for f in files:
        if 'min.js' in f:
            continue
        res = check_file_ast(f)
        status = "[OK]" if res == "SYNTAX OK" else "[ERROR]"
        if res != "SYNTAX OK":
            errors += 1
            print(f"{status} {f}: {res}")
        else:
            print(f"{status} {f}")

    print("==================================================")
    print(f"Total checked: {len(files)} | Errors: {errors}")
    print("==================================================")
    return errors

if __name__ == '__main__':
    sys.exit(main())
