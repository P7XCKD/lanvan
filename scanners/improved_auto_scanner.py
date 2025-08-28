#!/usr/bin/env python3
"""
Improved Auto Function Scanner - More accurate dependency detection
Identifies truly safe-to-extract functions with zero external dependencies
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

def find_function_dependencies(function_body, function_name, function_params=None):
    """Find all external dependencies used by a specific function"""
    
    if function_params is None:
        function_params = set()
    
    variable_refs = set()
    
    # Remove comments and strings to avoid false positives
    clean_body = re.sub(r'//.*$', '', function_body, flags=re.MULTILINE)
    clean_body = re.sub(r'/\*.*?\*/', '', clean_body, flags=re.DOTALL)
    clean_body = re.sub(r'"[^"]*"', '""', clean_body)
    clean_body = re.sub(r"'[^']*'", "''", clean_body)
    clean_body = re.sub(r'`[^`]*`', '``', clean_body)
    
    # Built-in JavaScript objects and functions that are safe
    builtins = {
        # Core JS objects
        'Date', 'Array', 'JSON', 'Object', 'String', 'Number', 'Boolean', 'Math', 
        'RegExp', 'Error', 'TypeError', 'ReferenceError', 'SyntaxError', 'RangeError',
        'WeakMap', 'WeakSet', 'Map', 'Set', 'Symbol', 'Proxy', 'Reflect',
        
        # Browser APIs (considered safe for utility functions)
        'console', 'localStorage', 'sessionStorage', 'window', 'navigator', 'document',
        'fetch', 'Promise', 'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
        'parseInt', 'parseFloat', 'isNaN', 'isFinite', 'encodeURIComponent', 'decodeURIComponent',
        'btoa', 'atob', 'Blob', 'FormData', 'URLSearchParams', 'URL', 'location', 'history',
        'alert', 'confirm', 'prompt', 'XMLHttpRequest', 'AbortController',
        
        # Safe method names 
        'toString', 'valueOf', 'toFixed', 'substring', 'substr', 'charAt', 'charCodeAt',
        'indexOf', 'lastIndexOf', 'slice', 'split', 'join', 'replace', 'match',
        'search', 'toLowerCase', 'toUpperCase', 'trim', 'push', 'pop', 'shift',
        'unshift', 'splice', 'concat', 'reverse', 'sort', 'filter', 'map', 'reduce',
        'forEach', 'find', 'findIndex', 'includes', 'some', 'every', 'length',
        'hasOwnProperty', 'propertyIsEnumerable', 'ceil', 'floor', 'round', 'abs',
        'min', 'max', 'pow', 'sqrt', 'random', 'log', 'exp', 'sin', 'cos', 'tan',
        
        # Safe keywords and literals
        'true', 'false', 'null', 'undefined', 'this', 'return', 'if', 'else',
        'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'try', 'catch',
        'finally', 'throw', 'new', 'var', 'let', 'const', 'function', 'async', 'await',
        'typeof', 'instanceof', 'in', 'of', 'delete', 'void'
    }
    
    # Find local variable declarations
    local_vars = set()
    local_patterns = [
        r'\b(?:var|let|const)\s+([a-zA-Z_][a-zA-Z_0-9]*)',
        r'for\s*\(\s*(?:var|let|const)?\s*([a-zA-Z_][a-zA-Z_0-9]*)',
        r'catch\s*\(\s*([a-zA-Z_][a-zA-Z_0-9]*)',
        r'([a-zA-Z_][a-zA-Z_0-9]*)\s*=',  # Assignment targets
        r'\{[^}]*\b([a-zA-Z_][a-zA-Z_0-9]*)\s*:',  # Object property names
    ]
    
    for pattern in local_patterns:
        for match in re.finditer(pattern, clean_body):
            if match.group(1):
                local_vars.add(match.group(1))
    
    # Add function parameters to local vars
    local_vars.update(function_params)
    local_vars.add(function_name)  # Function can reference itself
    
    # Check for DOM dependencies (major red flag)
    dom_patterns = [
        r'getElementById',
        r'querySelector',
        r'getElementsBy\w+',
        r'createElement',
        r'appendChild',
        r'removeChild',
        r'innerHTML',
        r'textContent',
        r'addEventListener',
        r'style\.',
    ]
    
    for pattern in dom_patterns:
        if re.search(pattern, clean_body):
            variable_refs.add('DOM_DEPENDENCY')
    
    # Patterns to find potential external dependencies
    dependency_patterns = [
        # Global variables (likely external state)
        r'\b([A-Z_][A-Z_0-9]{2,})\b',
        
        # Function calls to non-builtin functions
        r'\b([a-z][a-zA-Z_0-9]*)\s*\(',
        
        # Object property access that might be external
        r'\b([a-z][a-zA-Z_0-9]*)\s*\.',
        
        # CamelCase variables (often external)
        r'\b([a-z][a-zA-Z_0-9]*[A-Z][a-zA-Z_0-9]*)\b',
    ]
    
    # Find potential dependencies
    for pattern in dependency_patterns:
        for match in re.finditer(pattern, clean_body):
            var_name = match.group(1)
            
            # Skip if it's safe
            if (var_name in builtins or 
                var_name in local_vars or
                len(var_name) <= 2 or
                var_name.isdigit()):
                continue
                
            # Skip common local variable names
            common_locals = {
                'item', 'data', 'result', 'value', 'key', 'index', 'element', 'event',
                'error', 'response', 'status', 'size', 'length', 'type', 'name',
                'text', 'content', 'message', 'config', 'option', 'param'
            }
            
            if var_name.lower() in common_locals:
                continue
                
            variable_refs.add(var_name)
    
    return variable_refs

def analyze_all_functions(file_path):
    """Analyze all functions in a file and categorize them more accurately"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"🔍 Scanning all functions in: {file_path}")
        print("=" * 80)
        
        functions = extract_all_functions(content)
        
        safe_functions = []
        unsafe_functions = []
        
        for func_name, func_data in functions.items():
            dependencies = find_function_dependencies(
                func_data['body'], 
                func_name, 
                func_data['params']
            )
            
            func_info = {
                'name': func_name,
                'dependencies': dependencies,
                'async': func_data.get('async', False),
                'size': len(func_data['full_match']),
                'lines': func_data['full_match'].count('\n') + 1,
                'params': func_data['params']
            }
            
            # More strict classification
            if dependencies:
                unsafe_functions.append(func_info)
            else:
                safe_functions.append(func_info)
        
        # Sort by size (largest first) for better extraction planning
        safe_functions.sort(key=lambda x: x['size'], reverse=True)
        unsafe_functions.sort(key=lambda x: x['size'], reverse=True)
        
        print(f"📊 IMPROVED ANALYSIS RESULTS:")
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
                params_str = f"({', '.join(func['params'])})" if func['params'] else "()"
                print(f"✅ {async_marker}{func['name']}{params_str} - {func['lines']} lines ({func['size']} chars)")
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
        print("Usage: python improved_auto_scanner.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    safe_functions, unsafe_functions = analyze_all_functions(file_path)
    
    if safe_functions:
        print("\n🚀 EXTRACTION RECOMMENDATION:")
        print("=" * 80)
        print("Extract these functions in order (largest first):")
        for i, func in enumerate(safe_functions[:8], 1):
            async_marker = "async " if func['async'] else ""
            params_str = f"({', '.join(func['params'])})" if func['params'] else "()"
            print(f"{i}. {async_marker}{func['name']}{params_str} ({func['lines']} lines)")
        
        if len(safe_functions) > 8:
            print(f"   ... and {len(safe_functions)-8} more safe functions")
        
        print(f"\n📈 Potential reduction: {sum(f['lines'] for f in safe_functions)} lines")
    
    sys.exit(0)
