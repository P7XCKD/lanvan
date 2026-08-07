import sys, re
from pathlib import Path

js_dir = Path('app/static/js')
all_js = sorted([f for f in js_dir.rglob('*.js') if not f.name.endswith('.min.js')])

print("="*60)
print("PHASE 3 — STEP 4: DEPENDENCY & CIRCULAR DEPENDENCY AUDIT")
print("="*60)

# Build module dependency graph by looking at window.* usage vs window.* definitions
module_defs = {}
module_uses = {}

for filepath in all_js:
    rel = str(filepath.relative_to(js_dir))
    code = filepath.read_text(encoding='utf-8', errors='ignore')
    
    # Symbols exported on window by this module
    defs = set(re.findall(r'window\.([a-zA-Z0-9_$]+)\s*=', code))
    # Module namespace objects e.g. window.BreadcrumbNav = ...
    defs.update(re.findall(r'window\.([a-zA-Z0-9_$]+)\s*=\s*(?:Object\.freeze|{\s*|\(function)', code))
    
    module_defs[rel] = defs
    
    # Symbols referenced on window by this module
    uses = set(re.findall(r'window\.([a-zA-Z0-9_$]+)', code))
    module_uses[rel] = uses

# Build adjacency list: file_A -> file_B if file_A uses a symbol defined by file_B
graph = {f: set() for f in module_defs}
for file_a, uses in module_uses.items():
    for file_b, defs in module_defs.items():
        if file_a == file_b: continue
        # intersect uses of A with defs of B
        shared = uses.intersection(defs)
        if shared:
            graph[file_a].add(file_b)

print("Module Inter-Dependencies:")
for mod, deps in sorted(graph.items()):
    if deps:
        print(f"  • {mod} -> {', '.join(sorted(deps))}")

# Tarjan's or simple DFS cycle detection
cycles = []

def find_cycles(node, path, visited):
    path.append(node)
    visited.add(node)
    for neighbor in graph.get(node, []):
        if neighbor in path:
            cycle = path[path.index(neighbor):] + [neighbor]
            cycles.append(cycle)
        elif neighbor not in visited:
            find_cycles(neighbor, path, visited)
    path.pop()

visited_nodes = set()
for m in graph:
    if m not in visited_nodes:
        find_cycles(m, [], visited_nodes)

# Deduplicate cycles
unique_cycles = []
for c in cycles:
    min_idx = c.index(min(c[:-1]))
    normalized = tuple(c[min_idx:-1] + c[:min_idx] + [c[min_idx]])
    if normalized not in unique_cycles:
        unique_cycles.append(normalized)

print("\nCircular Dependencies Detected:")
if not unique_cycles:
    print("  ZERO CIRCULAR DEPENDENCIES DETECTED.")
else:
    for cycle in unique_cycles:
        print("  Cycle found:")
        for i in range(len(cycle)-1):
            print(f"    {cycle[i]} -> {cycle[i+1]}")
