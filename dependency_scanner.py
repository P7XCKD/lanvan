#!/usr/bin/env python3
"""
Dependency Detective Script
Scans JavaScript functions for external variable dependencies
"""

import re
import sys

def find_function_dependencies(js_code, function_name):
    """Find all variables used by a specific function"""
    
    # Extract the function body
    function_pattern = rf'function\s+{function_name}\s*\([^)]*\)\s*\{{(.*?)\n\s*\}}'
    match = re.search(function_pattern, js_code, re.DOTALL)
    
    if not match:
        return f"❌ Function '{function_name}' not found"
    
    function_body = match.group(1)
    
    # Find all variable references (excluding function parameters and local declarations)
    variable_refs = set()
    
    # Pattern for variable usage (excluding declarations)
    var_pattern = r'\b([A-Z_][A-Z_0-9]*)\b'  # UPPERCASE variables (likely constants)
    var_pattern2 = r'\b([a-zA-Z_][a-zA-Z_0-9]*)\s*\.'  # object.property access
    
    # Find UPPERCASE constants
    for match in re.finditer(var_pattern, function_body):
        var_name = match.group(1)
        if var_name not in ['Date', 'Array', 'JSON', 'Object', 'String', 'Number', 'Boolean', 'Math', 'console', 'localStorage', 'window', 'navigator']:
            variable_refs.add(var_name)
    
    # Find object references
    for match in re.finditer(var_pattern2, function_body):
        var_name = match.group(1)
        if var_name not in ['Date', 'Array', 'JSON', 'Object', 'String', 'Number', 'Boolean', 'Math', 'console', 'localStorage', 'window', 'navigator']:
            variable_refs.add(var_name)
    
    return variable_refs

def analyze_function(file_path, function_name):
    """Analyze a specific function for dependencies"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        dependencies = find_function_dependencies(content, function_name)
        
        if isinstance(dependencies, str):  # Error message
            print(dependencies)
            return False
        
        print(f"🔍 Analyzing function: {function_name}")
        print(f"📄 File: {file_path}")
        
        if dependencies:
            print(f"⚠️  External dependencies found: {', '.join(dependencies)}")
            return False
        else:
            print(f"✅ No external dependencies - SAFE TO EXTRACT!")
            return True
            
    except Exception as e:
        print(f"❌ Error analyzing file: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python dependency_scanner.py <file_path> <function_name>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    function_name = sys.argv[2]
    
    result = analyze_function(file_path, function_name)
    sys.exit(0 if result else 1)
