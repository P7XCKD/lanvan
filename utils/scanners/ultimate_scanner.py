#!/usr/bin/env python3
"""
Ultimate Extraction Scanner - Ultra-accurate multi-component analysis
Identifies extractable: JavaScript functions, CSS blocks, variable declarations, script sections
"""

import re
import sys
import json
from dataclasses import dataclass
from typing import List, Set, Dict, Tuple, Optional

@dataclass
class ExtractionCandidate:
    """Represents a potential extraction candidate"""
    type: str  # 'function', 'css', 'variable', 'script', 'constant'
    name: str
    content: str
    start_line: int
    end_line: int
    size_chars: int
    size_lines: int
    dependencies: Set[str]
    safety_score: int  # 0-100, higher = safer
    extraction_value: int  # 0-100, higher = more valuable to extract
    params: Set[str] = None

class UltimateScanner:
    def __init__(self):
        # JavaScript built-ins that are always safe
        self.js_builtins = {
            # Core objects
            'Date', 'Array', 'JSON', 'Object', 'String', 'Number', 'Boolean', 'Math', 
            'RegExp', 'Error', 'TypeError', 'ReferenceError', 'SyntaxError', 'RangeError',
            'WeakMap', 'WeakSet', 'Map', 'Set', 'Symbol', 'Proxy', 'Reflect',
            
            # Browser APIs
            'console', 'localStorage', 'sessionStorage', 'window', 'navigator', 'document',
            'fetch', 'Promise', 'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
            'parseInt', 'parseFloat', 'isNaN', 'isFinite', 'encodeURIComponent', 'decodeURIComponent',
            'btoa', 'atob', 'Blob', 'FormData', 'URLSearchParams', 'URL', 'location', 'history',
            'alert', 'confirm', 'prompt', 'XMLHttpRequest', 'AbortController',
            
            # Method names (usually safe)
            'toString', 'valueOf', 'toFixed', 'substring', 'substr', 'charAt', 'charCodeAt',
            'indexOf', 'lastIndexOf', 'slice', 'split', 'join', 'replace', 'match',
            'search', 'toLowerCase', 'toUpperCase', 'trim', 'push', 'pop', 'shift',
            'unshift', 'splice', 'concat', 'reverse', 'sort', 'filter', 'map', 'reduce',
            'forEach', 'find', 'findIndex', 'includes', 'some', 'every', 'length',
            'hasOwnProperty', 'propertyIsEnumerable', 'ceil', 'floor', 'round', 'abs',
            'min', 'max', 'pow', 'sqrt', 'random', 'log', 'exp', 'sin', 'cos', 'tan',
            
            # Keywords and literals
            'true', 'false', 'null', 'undefined', 'this', 'return', 'if', 'else',
            'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'try', 'catch',
            'finally', 'throw', 'new', 'var', 'let', 'const', 'function', 'async', 'await',
            'typeof', 'instanceof', 'in', 'of', 'delete', 'void', 'class', 'extends',
            'super', 'static', 'get', 'set', 'import', 'export', 'default'
        }
        
        # Common safe local variable names
        self.safe_local_names = {
            'i', 'j', 'k', 'x', 'y', 'z', 'item', 'data', 'result', 'value', 'key', 
            'index', 'element', 'event', 'error', 'response', 'status', 'size', 'length', 
            'type', 'name', 'text', 'content', 'message', 'config', 'option', 'param',
            'obj', 'arr', 'str', 'num', 'bool', 'func', 'callback', 'promise', 'timeout',
            'interval', 'id', 'className', 'style', 'attr', 'prop', 'val', 'temp'
        }

    def clean_code(self, code: str) -> str:
        """Remove comments and strings to avoid false positives"""
        # Remove single line comments
        cleaned = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        # Remove multi-line comments
        cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
        # Remove string literals
        cleaned = re.sub(r'"(?:[^"\\]|\\.)*"', '""', cleaned)
        cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "''", cleaned)
        cleaned = re.sub(r'`(?:[^`\\]|\\.)*`', '``', cleaned)
        return cleaned

    def extract_javascript_functions(self, content: str) -> List[ExtractionCandidate]:
        """Extract JavaScript functions with advanced parsing"""
        candidates = []
        
        # Enhanced regex for function extraction including arrow functions
        patterns = [
            # Regular functions: function name(params) { ... }
            r'(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*\{((?:[^{}]*(?:\{[^{}]*\})*)*)\}',
            # Arrow functions: const name = (params) => { ... }
            r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{((?:[^{}]*(?:\{[^{}]*\})*)*)\}',
            # Arrow functions: const name = param => { ... }
            r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(\w+)\s*=>\s*\{((?:[^{}]*(?:\{[^{}]*\})*)*)\}'
        ]
        
        lines = content.split('\n')
        
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.DOTALL | re.MULTILINE):
                func_name = match.group(1)
                
                # Extract parameters
                params = set()
                if len(match.groups()) >= 2 and match.group(2):
                    param_str = match.group(2)
                    for param in param_str.split(','):
                        param_name = param.strip().split('=')[0].strip()
                        if param_name and re.match(r'^[a-zA-Z_][a-zA-Z_0-9]*$', param_name):
                            params.add(param_name)
                
                # Get function body
                func_body = match.group(-1)  # Last group is always the body
                
                # Calculate line numbers
                start_pos = match.start()
                end_pos = match.end()
                start_line = content[:start_pos].count('\n') + 1
                end_line = content[:end_pos].count('\n') + 1
                
                # Analyze dependencies
                dependencies = self.analyze_js_dependencies(func_body, func_name, params)
                
                # Calculate safety and extraction value scores
                safety_score = self.calculate_safety_score(dependencies, func_body)
                extraction_value = self.calculate_extraction_value(func_body, func_name)
                
                candidate = ExtractionCandidate(
                    type='function',
                    name=func_name,
                    content=match.group(0),
                    start_line=start_line,
                    end_line=end_line,
                    size_chars=len(match.group(0)),
                    size_lines=end_line - start_line + 1,
                    dependencies=dependencies,
                    safety_score=safety_score,
                    extraction_value=extraction_value,
                    params=params
                )
                
                candidates.append(candidate)
        
        return candidates

    def extract_css_blocks(self, content: str) -> List[ExtractionCandidate]:
        """Extract standalone CSS blocks"""
        candidates = []
        
        # Find <style> blocks
        style_pattern = r'<style[^>]*>(.*?)</style>'
        
        for match in re.finditer(style_pattern, content, re.DOTALL):
            css_content = match.group(1).strip()
            if len(css_content) < 50:  # Skip tiny CSS blocks
                continue
                
            start_pos = match.start()
            end_pos = match.end()
            start_line = content[:start_pos].count('\n') + 1
            end_line = content[:end_pos].count('\n') + 1
            
            # Analyze CSS for dependencies (like @import, url(), etc.)
            dependencies = self.analyze_css_dependencies(css_content)
            
            # CSS blocks are generally safe to extract
            safety_score = 85 if not dependencies else 60
            extraction_value = min(90, len(css_content) // 10)  # Value based on size
            
            candidate = ExtractionCandidate(
                type='css',
                name=f'css_block_{start_line}',
                content=match.group(0),
                start_line=start_line,
                end_line=end_line,
                size_chars=len(match.group(0)),
                size_lines=end_line - start_line + 1,
                dependencies=dependencies,
                safety_score=safety_score,
                extraction_value=extraction_value
            )
            
            candidates.append(candidate)
        
        return candidates

    def extract_variable_declarations(self, content: str) -> List[ExtractionCandidate]:
        """Extract standalone variable and constant declarations"""
        candidates = []
        
        # Patterns for different types of variables
        patterns = [
            # const CONSTANT = value;
            r'(?:^|\n)\s*(const\s+[A-Z_][A-Z_0-9]*\s*=\s*[^;]+;)',
            # let/var configurations
            r'(?:^|\n)\s*((?:let|var)\s+\w+Config\s*=\s*\{[^}]+\};)',
            # Standalone object literals
            r'(?:^|\n)\s*(const\s+\w+\s*=\s*\{(?:[^{}]*(?:\{[^{}]*\})*)*\};)'
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                var_content = match.group(1).strip()
                
                # Extract variable name
                var_name_match = re.search(r'(?:const|let|var)\s+(\w+)', var_content)
                if not var_name_match:
                    continue
                    
                var_name = var_name_match.group(1)
                
                start_pos = match.start()
                end_pos = match.end()
                start_line = content[:start_pos].count('\n') + 1
                end_line = content[:end_pos].count('\n') + 1
                
                # Analyze dependencies
                dependencies = self.analyze_variable_dependencies(var_content, var_name)
                
                safety_score = 80 if not dependencies else 40
                extraction_value = 70  # Variables are valuable for organization
                
                candidate = ExtractionCandidate(
                    type='variable',
                    name=var_name,
                    content=var_content,
                    start_line=start_line,
                    end_line=end_line,
                    size_chars=len(var_content),
                    size_lines=end_line - start_line + 1,
                    dependencies=dependencies,
                    safety_score=safety_score,
                    extraction_value=extraction_value
                )
                
                candidates.append(candidate)
        
        return candidates

    def analyze_js_dependencies(self, code: str, func_name: str, params: Set[str]) -> Set[str]:
        """Analyze JavaScript code for external dependencies"""
        dependencies = set()
        cleaned_code = self.clean_code(code)
        
        # Find local variables
        local_vars = set(params) if params else set()
        local_vars.add(func_name)
        
        # Local variable patterns
        local_patterns = [
            r'\b(?:var|let|const)\s+([a-zA-Z_][a-zA-Z_0-9]*)',
            r'for\s*\(\s*(?:var|let|const)?\s*([a-zA-Z_][a-zA-Z_0-9]*)',
            r'catch\s*\(\s*([a-zA-Z_][a-zA-Z_0-9]*)',
            r'([a-zA-Z_][a-zA-Z_0-9]*)\s*=',
            r'function\s+([a-zA-Z_][a-zA-Z_0-9]*)',
        ]
        
        for pattern in local_patterns:
            for match in re.finditer(pattern, cleaned_code):
                if match.group(1):
                    local_vars.add(match.group(1))
        
        # Add safe local names
        local_vars.update(self.safe_local_names)
        
        # Dependency detection patterns
        dependency_patterns = [
            # Global variables (UPPERCASE)
            r'\b([A-Z_][A-Z_0-9]{2,})\b',
            # Function calls
            r'\b([a-z][a-zA-Z_0-9]*)\s*\(',
            # Object property access
            r'\b([a-z][a-zA-Z_0-9]*)\s*\.',
            # camelCase variables
            r'\b([a-z][a-zA-Z_0-9]*[A-Z][a-zA-Z_0-9]*)\b',
        ]
        
        # Check for DOM dependencies
        dom_indicators = [
            'getElementById', 'querySelector', 'createElement', 'appendChild',
            'innerHTML', 'textContent', 'style.', 'classList', 'addEventListener'
        ]
        
        for indicator in dom_indicators:
            if indicator in cleaned_code:
                dependencies.add('DOM_DEPENDENCY')
                break
        
        # Find potential external dependencies
        for pattern in dependency_patterns:
            for match in re.finditer(pattern, cleaned_code):
                var_name = match.group(1)
                
                if (var_name not in self.js_builtins and 
                    var_name not in local_vars and
                    len(var_name) > 2 and
                    not var_name.isdigit()):
                    dependencies.add(var_name)
        
        return dependencies

    def analyze_css_dependencies(self, css_code: str) -> Set[str]:
        """Analyze CSS for external dependencies"""
        dependencies = set()
        
        # Check for external resources
        if re.search(r'@import|url\(', css_code):
            dependencies.add('EXTERNAL_RESOURCES')
        
        # Check for CSS variables that might be external
        css_vars = re.findall(r'var\((--[^)]+)\)', css_code)
        for var in css_vars:
            dependencies.add(f'CSS_VAR_{var}')
        
        return dependencies

    def analyze_variable_dependencies(self, var_code: str, var_name: str) -> Set[str]:
        """Analyze variable declarations for dependencies"""
        dependencies = set()
        cleaned_code = self.clean_code(var_code)
        
        # Look for references to external variables
        external_refs = re.findall(r'\b([a-zA-Z_][a-zA-Z_0-9]*)\b', cleaned_code)
        
        for ref in external_refs:
            if (ref not in self.js_builtins and
                ref != var_name and
                ref not in self.safe_local_names and
                len(ref) > 2):
                dependencies.add(ref)
        
        return dependencies

    def calculate_safety_score(self, dependencies: Set[str], code: str) -> int:
        """Calculate safety score (0-100, higher = safer)"""
        base_score = 100
        
        # Penalty for dependencies
        base_score -= len(dependencies) * 15
        
        # Penalty for DOM usage
        if 'DOM_DEPENDENCY' in dependencies:
            base_score -= 30
        
        # Penalty for complex code patterns
        complexity_indicators = ['fetch(', 'XMLHttpRequest', 'addEventListener', 'setTimeout']
        for indicator in complexity_indicators:
            if indicator in code:
                base_score -= 10
        
        return max(0, min(100, base_score))

    def calculate_extraction_value(self, code: str, name: str) -> int:
        """Calculate extraction value (0-100, higher = more valuable)"""
        base_value = 50
        
        # Value based on size (longer functions more valuable to extract)
        size_bonus = min(30, len(code) // 50)
        base_value += size_bonus
        
        # Bonus for utility function patterns
        utility_patterns = ['format', 'convert', 'parse', 'validate', 'calculate', 'get', 'check']
        if any(pattern in name.lower() for pattern in utility_patterns):
            base_value += 20
        
        # Bonus for pure functions (mathematical operations, string manipulation)
        pure_indicators = ['Math.', 'String.', 'Array.', 'return ', '.map(', '.filter(', '.reduce(']
        pure_count = sum(1 for indicator in pure_indicators if indicator in code)
        base_value += pure_count * 5
        
        return min(100, base_value)

    def scan_file(self, file_path: str) -> Dict[str, List[ExtractionCandidate]]:
        """Scan file for all extraction opportunities"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            return {}
        
        results = {
            'functions': self.extract_javascript_functions(content),
            'css_blocks': self.extract_css_blocks(content),
            'variables': self.extract_variable_declarations(content)
        }
        
        return results

    def generate_report(self, results: Dict[str, List[ExtractionCandidate]]) -> None:
        """Generate comprehensive extraction report"""
        print("🔍 ULTIMATE EXTRACTION SCANNER RESULTS")
        print("=" * 80)
        
        # Summary statistics
        total_candidates = sum(len(candidates) for candidates in results.values())
        safe_candidates = []
        
        for category, candidates in results.items():
            safe_in_category = [c for c in candidates if c.safety_score >= 70]
            safe_candidates.extend(safe_in_category)
        
        print(f"📊 SUMMARY:")
        print(f"   Total Extraction Opportunities: {total_candidates}")
        print(f"   ✅ Safe Extractions (Score ≥70): {len(safe_candidates)}")
        print(f"   📏 Potential Line Reduction: {sum(c.size_lines for c in safe_candidates)}")
        print()
        
        # Detailed breakdown by category
        for category, candidates in results.items():
            if not candidates:
                continue
                
            print(f"🎯 {category.upper().replace('_', ' ')}:")
            print("-" * 50)
            
            # Sort by extraction value
            sorted_candidates = sorted(candidates, key=lambda x: x.extraction_value, reverse=True)
            
            for candidate in sorted_candidates[:10]:  # Show top 10
                safety_emoji = "✅" if candidate.safety_score >= 70 else "⚠️" if candidate.safety_score >= 50 else "❌"
                deps_str = ", ".join(list(candidate.dependencies)[:3])
                if len(candidate.dependencies) > 3:
                    deps_str += f"... (+{len(candidate.dependencies)-3})"
                
                print(f"{safety_emoji} {candidate.name} - {candidate.size_lines} lines "
                      f"(Safety: {candidate.safety_score}/100, Value: {candidate.extraction_value}/100)")
                if candidate.dependencies:
                    print(f"     Dependencies: {deps_str}")
            
            if len(sorted_candidates) > 10:
                print(f"   ... and {len(sorted_candidates) - 10} more candidates")
            print()
        
        # Top extraction recommendations
        all_safe = [c for candidates in results.values() for c in candidates if c.safety_score >= 70]
        if all_safe:
            print("🚀 TOP EXTRACTION RECOMMENDATIONS:")
            print("=" * 80)
            
            # Sort by combined score
            top_candidates = sorted(all_safe, key=lambda x: x.safety_score + x.extraction_value, reverse=True)
            
            for i, candidate in enumerate(top_candidates[:8], 1):
                params_str = f"({', '.join(candidate.params)})" if candidate.params else ""
                print(f"{i}. [{candidate.type.upper()}] {candidate.name}{params_str}")
                print(f"   Lines: {candidate.size_lines} | Safety: {candidate.safety_score}/100 | Value: {candidate.extraction_value}/100")
                if candidate.dependencies:
                    deps_str = ", ".join(list(candidate.dependencies)[:3])
                    print(f"   Dependencies: {deps_str}")
                print()

def main():
    if len(sys.argv) != 2:
        print("Usage: python ultimate_scanner.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    scanner = UltimateScanner()
    results = scanner.scan_file(file_path)
    scanner.generate_report(results)

if __name__ == "__main__":
    main()
