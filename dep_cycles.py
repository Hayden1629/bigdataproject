import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple


def _build_module_map(root: Path, package: str) -> Dict[str, Path]:
    modules: Dict[str, Path] = {}
    for path in root.rglob("*.py"):
        if path.name.startswith("_"):
            continue
        rel = path.relative_to(root)
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            continue
        mod = ".".join([package] + parts)
        modules[mod] = path
    return modules


def _resolve_relative(module: str, level: int, target: str | None) -> str | None:
    parts = module.split(".")
    if level > len(parts):
        return None
    base = parts[:-level]
    if target:
        base += target.split(".")
    if not base:
        return None
    return ".".join(base)


def _build_graph(modules: Dict[str, Path]) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = {m: set() for m in modules}

    # map short name -> full modules (for bare imports like `import logger`)
    short_to_full: Dict[str, List[str]] = {}
    for full in modules:
        short = full.split(".")[-1]
        short_to_full.setdefault(short, []).append(full)

    for mod, path in modules.items():
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(path))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    for cand in short_to_full.get(top, []):
                        if cand != mod:
                            graph[mod].add(cand)

            elif isinstance(node, ast.ImportFrom):
                target_mod: str | None
                if node.level:
                    target_mod = _resolve_relative(mod, node.level, node.module)
                else:
                    target_mod = node.module

                if not target_mod:
                    continue

                # direct match
                if target_mod in modules and target_mod != mod:
                    graph[mod].add(target_mod)

                # submodules inside a package import
                prefix = target_mod + "."
                for cand in modules:
                    if cand.startswith(prefix) and cand != mod:
                        graph[mod].add(cand)

    return graph


def _find_cycles(graph: Dict[str, Set[str]]) -> List[Tuple[str, ...]]:
    visited: Set[str] = set()
    stack: List[str] = []
    onstack: Set[str] = set()
    cycles: Set[Tuple[str, ...]] = set()

    def dfs(node: str) -> None:
        visited.add(node)
        stack.append(node)
        onstack.add(node)
        for nxt in graph.get(node, ()):
            if nxt not in graph:
                continue
            if nxt not in visited:
                dfs(nxt)
            elif nxt in onstack:
                try:
                    idx = stack.index(nxt)
                except ValueError:
                    continue
                cyc = tuple(stack[idx:] + [nxt])
                # normalise cycle rotation for stable identity
                min_idx = min(range(len(cyc) - 1), key=lambda i: cyc[i])
                norm = cyc[min_idx:-1] + cyc[:min_idx] + (cyc[min_idx],)
                cycles.add(norm)
        stack.pop()
        onstack.remove(node)

    for node in graph:
        if node not in visited:
            dfs(node)

    return sorted(cycles)


def main() -> None:
    root = Path(__file__).parent / "dashboard"
    if not root.exists():
        raise SystemExit("dashboard package not found next to dep_cycles.py")

    modules = _build_module_map(root, "dashboard")
    graph = _build_graph(modules)
    cycles = _find_cycles(graph)

    if not cycles:
        print("No import cycles detected within dashboard.")
        return

    print("Import cycles detected within dashboard (module-level):")
    for cyc in cycles:
        print("  - " + " -> ".join(cyc))


if __name__ == "__main__":
    main()

