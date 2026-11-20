import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
FORBIDDEN = ("token", "secret", "password", "api_key", "apikey", "authorization", "credential")


def _trees():
    files = sorted(SRC.rglob("*.py"))
    assert files
    for f in files:
        yield f, ast.parse(f.read_text(), filename=str(f))


def test_no_print_calls():  # MCP-008: stdout is JSON-RPC only
    bad = [f"{f}:{n.lineno}" for f, t in _trees() for n in ast.walk(t)
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"]
    assert not bad, bad


def _is_tool_decorator(d):
    d = d.func if isinstance(d, ast.Call) else d
    return isinstance(d, ast.Attribute) and d.attr == "tool"


def test_tool_functions_have_no_credential_params():  # MCP-001
    found = 0
    bad = []
    for f, t in _trees():
        for n in ast.walk(t):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                    _is_tool_decorator(d) for d in n.decorator_list):
                found += 1
                a = n.args
                for arg in a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x]:
                    if any(w in arg.arg.lower() for w in FORBIDDEN):
                        bad.append(f"{f}:{n.lineno} {n.name}({arg.arg})")
    assert found >= 4, "tool detection failed"
    assert not bad, bad
