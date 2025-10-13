#!/usr/bin/env python3
"""
Ultimate Scanner v3 - Fast Function Extraction
Optimized for speed and efficiency
"""

import re
import sys

def extract_functions_fast(content):
    """Fast function extraction with minimal processing"""
    functions = []
    
    # Simple regex for function detection - much faster
    function_pattern = r'function\s+(\w+)\s*\([^)]*\)\s*\{'
    
    for match in re.finditer(function_pattern, content):
        func_name = match.group(1)
        start_pos = match.start()
        
        # Find function end by counting braces - faster than complex parsing
        brace_count = 0
        func_start = start_pos
        func_end = start_pos
        
        for i, char in enumerate(content[start_pos:], start_pos):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    func_end = i + 1
                    break
        
        func_content = content[func_start:func_end]
        
        # Quick dependency check - only check for obvious patterns
        has_dom = bool(re.search(r'document\.|getElementById|querySelector', func_content))
        has_global_vars = bool(re.search(r'DOM_CACHE|LANVAN_CONFIG|showToast', func_content))
        has_template_vars = bool(re.search(r'\{\{.*?\}\}', func_content))
        
        # Quick safety assessment
        is_safe = (
            not has_template_vars and
            len(func_content) > 50 and  # Not too small
            len(func_content) < 2000 and  # Not too large
            func_name not in ['main', 'init', 'setup']  # Not core functions
        )
        
        functions.append({
            'name': func_name,
            'content': func_content,
            'lines': func_content.count('\n') + 1,
            'size': len(func_content),
            'safe': is_safe,
            'has_dom': has_dom,
            'has_globals': has_global_vars,
            'issues': [] if is_safe else ['Template vars' if has_template_vars else 'Size/Core function']
        })
    
    return functions

def analyze_template_fast(file_path):
    """Fast template analysis focused on function extraction"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"🚀 Ultimate Scanner v3 - Fast Analysis: {file_path}")
        print("=" * 60)
        
        # Quick stats
        total_lines = content.count('\n') + 1
        total_chars = len(content)
        
        print(f"📊 TEMPLATE STATS:")
        print(f"   Lines: {total_lines:,}")
        print(f"   Size: {total_chars:,} chars")
        print()
        
        # Extract functions quickly
        print("🔍 Extracting functions...")
        functions = extract_functions_fast(content)
        
        safe_functions = [f for f in functions if f['safe']]
        unsafe_functions = [f for f in functions if not f['safe']]
        
        print(f"📋 FUNCTION ANALYSIS:")
        print(f"   Total Functions: {len(functions)}")
        print(f"   Safe to Extract: {len(safe_functions)}")
        print(f"   Unsafe: {len(unsafe_functions)}")
        print()
        
        if safe_functions:
            total_safe_lines = sum(f['lines'] for f in safe_functions)
            potential_reduction = (total_safe_lines / total_lines) * 100
            
            print(f"🎯 EXTRACTION POTENTIAL:")
            print(f"   Extractable Lines: {total_safe_lines:,}")
            print(f"   Potential Reduction: {potential_reduction:.1f}%")
            print()
            
            print(f"✅ TOP SAFE FUNCTIONS (Ready for extraction):")
            print("-" * 50)
            
            # Sort by size and show top candidates
            safe_functions.sort(key=lambda x: x['lines'], reverse=True)
            for i, func in enumerate(safe_functions[:10], 1):
                dom_icon = "🌐" if func['has_dom'] else "📝"
                global_icon = "🔗" if func['has_globals'] else "⚡"
                
                print(f"{i:2d}. {dom_icon}{global_icon} {func['name']}")
                print(f"     Size: {func['lines']} lines ({func['size']} chars)")
                if i <= 5:  # Show first 5 in detail
                    print(f"     Preview: {func['content'][:50].strip()}...")
                print()
        
        if unsafe_functions:
            print(f"⚠️  UNSAFE FUNCTIONS (Not recommended):")
            print("-" * 40)
            for func in unsafe_functions[:5]:
                print(f"   • {func['name']} - {func['issues'][0] if func['issues'] else 'Unknown issue'}")
        
        print(f"🎯 NEXT STEPS:")
        if safe_functions:
            best = safe_functions[0]
            print(f"   1. Extract '{best['name']}' function ({best['lines']} lines)")
            print(f"   2. Test functionality")
            print(f"   3. Continue with next functions")
        else:
            print(f"   No safe functions found for extraction")
        
        return functions
        
    except Exception as e:
        print(f"❌ Error analyzing file: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python ultimate_scanner.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    analyze_template_fast(file_path)
