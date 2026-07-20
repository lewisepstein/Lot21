"""Classify FastAPI route functions: which async def routes are safe to convert to def.

A route is CONVERTIBLE only if it is async, contains no await/async-with/async-for/yield,
and is not wrapped by @require_session_auth (whose wrapper awaits the callee).
"""
import ast
import os
from pathlib import Path

APP = str(Path(__file__).resolve().parent.parent / "app")
HTTP = {"get", "post", "put", "patch", "delete"}


def deco_is_route(d):
    f = d.func if isinstance(d, ast.Call) else d
    return (
        isinstance(f, ast.Attribute)
        and f.attr in HTTP
        and isinstance(f.value, ast.Name)
        and f.value.id in {"router", "app"}
    )


class AwaitFinder(ast.NodeVisitor):
    def __init__(self):
        self.awaits = []

    def visit_Await(self, node):
        v = node.value
        name = None
        if isinstance(v, ast.Call):
            fn = v.func
            if isinstance(fn, ast.Attribute):
                name = fn.attr
            elif isinstance(fn, ast.Name):
                name = fn.id
        self.awaits.append(name or "<expr>")
        self.generic_visit(node)

    def visit_AsyncWith(self, node):
        self.awaits.append("<async with>")
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self.awaits.append("<async for>")
        self.generic_visit(node)

    def visit_Yield(self, node):
        self.awaits.append("<yield>")
        self.generic_visit(node)

    def visit_YieldFrom(self, node):
        self.awaits.append("<yield from>")
        self.generic_visit(node)

    def visit_FunctionDef(self, n):
        pass

    def visit_AsyncFunctionDef(self, n):
        pass


def _is_rsa(d):
    f = d.func if isinstance(d, ast.Call) else d
    return (isinstance(f, ast.Name) and f.id == "require_session_auth") or (
        isinstance(f, ast.Attribute) and f.attr == "require_session_auth"
    )


rows = []
for root, _, files in os.walk(APP):
    if "/alembic" in root or "__pycache__" in root:
        continue
    for fn in files:
        if not fn.endswith(".py"):
            continue
        p = os.path.join(root, fn)
        try:
            tree = ast.parse(open(p, encoding="utf-8").read())
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(deco_is_route(d) for d in node.decorator_list):
                    is_async = isinstance(node, ast.AsyncFunctionDef)
                    af = AwaitFinder()
                    for stmt in node.body:
                        af.visit(stmt)
                    rsa = any(_is_rsa(d) for d in node.decorator_list)
                    rel = p.replace(APP + "/", "")
                    rows.append((rel, node.lineno, node.name, is_async, af.awaits, rsa))

convertible = [r for r in rows if r[3] and not r[4] and not r[5]]
excluded_async_construct = [r for r in rows if r[3] and r[4]]
excluded_decorated = [r for r in rows if r[3] and not r[4] and r[5]]
sync_defs = [r for r in rows if not r[3]]

print(f"TOTAL route functions: {len(rows)}")
print(f"  CONVERTIBLE (async, no async-construct, not @require_session_auth): {len(convertible)}")
print(f"  EXCLUDED - has await/async-with/async-for/yield: {len(excluded_async_construct)}")
print(f"  EXCLUDED - @require_session_auth (wrapper awaits it): {len(excluded_decorated)}")
print(f"  already plain def: {len(sync_defs)}")

print("\n===== CONVERTIBLE async def -> def =====")
for rel, ln, name, *_ in sorted(convertible):
    print(f"{rel}:{ln}  {name}")

print("\n===== EXCLUDED: async construct in body =====")
for rel, ln, name, _, aw, _ in sorted(excluded_async_construct):
    print(f"{rel}:{ln}  {name}  -> {sorted(set(aw))}")

print("\n===== EXCLUDED: @require_session_auth =====")
for rel, ln, name, *_ in sorted(excluded_decorated):
    print(f"{rel}:{ln}  {name}")
