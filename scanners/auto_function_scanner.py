#!/usr/bin/env python3
"""
Auto Function Scanner - Analyze ALL JavaScript functions in a file
Identifies safe-to-extract functions with zero external dependencies
"""

import re
import sys

def extract_all_functions(js_code):
    """Extract all function definitions from JavaScript code with better parsing"""
    functions = {}
    
    # More comprehensive function pattern that handles nested braces better
    function_pattern = r'(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*\{((?:[^{}]*+(?:\{(?:[^{}]*+(?:\{[^{}]*+\})*[^{}]*+)*\})*[^{}]*+)*)\}'
    
    for match in re.finditer(function_pattern, js_code, re.DOTALL):
        is_async = match.group(0).strip().startswith('async')
        func_name = match.group(1)
        params = match.group(2)
        func_body = match.group(3)
        
        # Extract parameter names
        param_names = set()
        if params.strip():
            for param in params.split(','):
                param_name = param.strip().split('=')[0].strip()
                if param_name and re.match(r'^[a-zA-Z_][a-zA-Z_0-9]*$', param_name):
                    param_names.add(param_name)
        
        functions[func_name] = {
            'body': func_body,
            'params': param_names,
            'full_match': match.group(0),
            'start': match.start(),
            'end': match.end(),
            'async': is_async
        }
    
    return functions

def find_function_dependencies(function_body, function_name):
    """Find all variables used by a specific function"""
    
    variable_refs = set()
    
    # Enhanced patterns for variable detection
    patterns = [
        # UPPERCASE constants (but exclude common string literals)
        r'\b([A-Z_][A-Z_0-9]{2,})\b',  # At least 3 chars for constants
        # Object property access (but not method calls)
        r'\b([a-zA-Z_][a-zA-Z_0-9]*)\s*\.[a-zA-Z]',
        # Function calls (external functions)
        r'\b([a-zA-Z_][a-zA-Z_0-9]*)\s*\(',
        # Global variable assignments
        r'\b(window\.[a-zA-Z_][a-zA-Z_0-9]*)',
        r'\b(document\.[a-zA-Z_][a-zA-Z_0-9]*)'
    ]
    
    # Built-in JavaScript objects and functions that are safe
    builtins = {
        'Date', 'Array', 'JSON', 'Object', 'String', 'Number', 'Boolean', 'Math', 
        'console', 'localStorage', 'sessionStorage', 'window', 'navigator', 'document',
        'fetch', 'Promise', 'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
        'parseInt', 'parseFloat', 'isNaN', 'isFinite', 'encodeURIComponent', 'decodeURIComponent',
        'btoa', 'atob', 'Blob', 'FormData', 'URLSearchParams', 'URL', 'location', 'history',
        'alert', 'confirm', 'prompt', 'XMLHttpRequest', 'AbortController', 'Error',
        'TypeError', 'ReferenceError', 'SyntaxError', 'RangeError', 'RegExp',
        'WeakMap', 'WeakSet', 'Map', 'Set', 'Symbol', 'Proxy', 'Reflect',
        # Common method names that are usually safe
        'toString', 'valueOf', 'toFixed', 'substring', 'substr', 'charAt', 'charCodeAt',
        'indexOf', 'lastIndexOf', 'slice', 'split', 'join', 'replace', 'match',
        'search', 'toLowerCase', 'toUpperCase', 'trim', 'push', 'pop', 'shift',
        'unshift', 'splice', 'concat', 'reverse', 'sort', 'filter', 'map', 'reduce',
        'forEach', 'find', 'findIndex', 'includes', 'some', 'every', 'length',
        'hasOwnProperty', 'propertyIsEnumerable', 'ceil', 'floor', 'round', 'abs',
        'min', 'max', 'pow', 'sqrt', 'random', 'log', 'exp', 'sin', 'cos', 'tan',
        # Safe literals and keywords
        'true', 'false', 'null', 'undefined', 'this', 'return', 'if', 'else',
        'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'try', 'catch',
        'finally', 'throw', 'new', 'var', 'let', 'const', 'function', 'async', 'await'
    }
    
    # Local variable patterns (declared within function)
    local_vars = set()
    
    # Find local variable declarations - more comprehensive
    local_patterns = [
        r'\b(?:var|let|const)\s+([a-zA-Z_][a-zA-Z_0-9]*)',
        r'function\s+([a-zA-Z_][a-zA-Z_0-9]*)',
        r'for\s*\(\s*(?:var|let|const)?\s*([a-zA-Z_][a-zA-Z_0-9]*)',
        r'catch\s*\(\s*([a-zA-Z_][a-zA-Z_0-9]*)',
        r'([a-zA-Z_][a-zA-Z_0-9]*)\s*=',  # Assignment targets
        r'function\s*\([^)]*\b([a-zA-Z_][a-zA-Z_0-9]*)\b[^)]*\)',  # Parameters
        r'\{[^}]*\b([a-zA-Z_][a-zA-Z_0-9]*)\s*:', # Object property shorthand
    ]
    
    for pattern in local_patterns:
        for match in re.finditer(pattern, function_body):
            local_vars.add(match.group(1))
    
    # Find all variable references but be more selective
    for pattern in patterns:
        for match in re.finditer(pattern, function_body):
            var_name = match.group(1)
            
            # Clean up the variable name
            if '.' in var_name:
                var_name = var_name.split('.')[0]
            
            # Skip if it's a builtin, local var, or the function itself
            if (var_name not in builtins and 
                var_name not in local_vars and 
                var_name != function_name and
                len(var_name) > 1 and  # Skip single letters
                not var_name.isdigit() and  # Skip numbers
                not re.match(r'^[A-Z]{1,2}$', var_name)):  # Skip short acronyms like 'GB', 'MB'
                
                # Extra filtering for common safe patterns
                if not any(safe_word in var_name.lower() for safe_word in 
                          ['element', 'event', 'error', 'result', 'response', 'data']):
                    variable_refs.add(var_name)
    
    return variable_refs

def analyze_all_functions(file_path):
    """Analyze all functions in a file and categorize them"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"🔍 Scanning all functions in: {file_path}")
        print("=" * 80)
        
        functions = extract_all_functions(content)
        
        safe_functions = []
        unsafe_functions = []
        
        for func_name, func_data in functions.items():
            dependencies = find_function_dependencies(func_data['body'], func_name)
            
            func_info = {
                'name': func_name,
                'dependencies': dependencies,
                'async': func_data.get('async', False),
                'size': len(func_data['full_match']),
                'lines': func_data['full_match'].count('\n') + 1
            }
            
            if dependencies:
                unsafe_functions.append(func_info)
            else:
                safe_functions.append(func_info)
        
        # Sort by size (largest first) for better extraction planning
        safe_functions.sort(key=lambda x: x['size'], reverse=True)
        unsafe_functions.sort(key=lambda x: x['size'], reverse=True)
        
        print(f"📊 ANALYSIS RESULTS:")
        print(f"   Total Functions: {len(functions)}")
        print(f"   ✅ Safe to Extract: {len(safe_functions)}")
        print(f"   ⚠️  Has Dependencies: {len(unsafe_functions)}")
        print()
        
        if safe_functions:
            print("🎯 SAFE TO EXTRACT (Zero Dependencies):")
            print("-" * 50)
            total_safe_lines = 0
            for func in safe_functions:
                async_marker = "async " if func['async'] else ""
                print(f"✅ {async_marker}{func['name']} - {func['lines']} lines ({func['size']} chars)")
                total_safe_lines += func['lines']
            
            print(f"\n💡 Total extractable lines: {total_safe_lines}")
            print()
        
        if unsafe_functions:
            print("⚠️  FUNCTIONS WITH DEPENDENCIES (Not Safe):")
            print("-" * 50)
            for func in unsafe_functions[:10]:  # Show top 10
                async_marker = "async " if func['async'] else ""
                deps = ", ".join(list(func['dependencies'])[:5])
                if len(func['dependencies']) > 5:
                    deps += f"... (+{len(func['dependencies'])-5} more)"
                print(f"❌ {async_marker}{func['name']} - Dependencies: {deps}")
            
            if len(unsafe_functions) > 10:
                print(f"   ... and {len(unsafe_functions)-10} more functions with dependencies")
        
        return safe_functions, unsafe_functions
        
    except Exception as e:
        print(f"❌ Error analyzing file: {e}")
        return [], []

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python auto_function_scanner.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    safe_functions, unsafe_functions = analyze_all_functions(file_path)
    
    if safe_functions:
        print("\n🚀 EXTRACTION RECOMMENDATION:")
        print("=" * 80)
        print("Extract these functions in order (largest first):")
        for i, func in enumerate(safe_functions[:5], 1):
            async_marker = "async " if func['async'] else ""
            print(f"{i}. {async_marker}{func['name']} ({func['lines']} lines)")
        
        if len(safe_functions) > 5:
            print(f"   ... and {len(safe_functions)-5} more safe functions")
    
    sys.exit(0)
