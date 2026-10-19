"""Тест для правила `self.method()` в методе класса.

Проверяет, что:
1. self._wrap() в Formatter.format резолвится в tiny_pkg.b.Formatter._wrap
2. Вызов имеет статус internal
3. callers и references работают корректно
"""

from pathlib import Path

from repo_map.index import RepoIndex

FIXTURE = Path(__file__).parent / "fixtures" / "tiny_pkg"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def test_self_method_definition():
    """Метод _wrap должен быть в индексе."""
    idx = build_index()

    results = idx.definition("tiny_pkg.b.Formatter._wrap")
    assert len(results) == 1
    assert results[0].qualified_name == "tiny_pkg.b.Formatter._wrap"
    assert results[0].kind == "method"
    assert results[0].file == "tiny_pkg/b.py"
    assert results[0].line == 13


def test_format_calls_wrap():
    """Formatter.format должен вызывать self._wrap."""
    idx = build_index()

    result = idx.callees("tiny_pkg.b.Formatter.format")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "tiny_pkg.b.Formatter._wrap" in internal_names, (
        f"self._wrap должен резолвиться в Formatter._wrap, но получено: {internal_names}"
    )


def test_self_method_call_status():
    """Вызов self._wrap() должен иметь статус internal."""
    idx = build_index()

    wrap_calls = [
        cs
        for cs in idx.call_sites("tiny_pkg.b.Formatter.format")
        if cs.target == "tiny_pkg.b.Formatter._wrap"
    ]
    assert len(wrap_calls) == 1
    assert wrap_calls[0].resolution == "internal"
    assert wrap_calls[0].expression == "self._wrap"


def test_callers_of_wrap():
    """callers для _wrap должен включать Formatter.format."""
    idx = build_index()

    callers = idx.callers("tiny_pkg.b.Formatter._wrap")
    caller_names = [c.qualified_name for c in callers]

    assert "tiny_pkg.b.Formatter.format" in caller_names, (
        f"Formatter.format должен быть среди callers для _wrap, но получено: {caller_names}"
    )


def test_references_of_wrap():
    """references для _wrap должен включать вызов из format."""
    idx = build_index()

    refs = idx.references("tiny_pkg.b.Formatter._wrap")

    call_refs = [r for r in refs if r.kind == "call"]
    assert len(call_refs) > 0, "Ожидался хотя бы один call reference"

    call_scopes = [r.scope for r in call_refs]
    assert "tiny_pkg.b.Formatter.format" in call_scopes, (
        f"Formatter.format должен быть среди scope в references, но получено: {call_scopes}"
    )


def test_format_also_calls_helper():
    """Formatter.format также вызывает helper (для полноты проверки)."""
    idx = build_index()

    result = idx.callees("tiny_pkg.b.Formatter.format")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "tiny_pkg.b.helper" in internal_names, (
        f"helper должен быть среди callees для format, но получено: {internal_names}"
    )


def test_wrap_is_method_not_function():
    """_wrap должен быть method, а не function."""
    idx = build_index()

    results = idx.definition("tiny_pkg.b.Formatter._wrap")
    assert results[0].kind == "method", f"Ожидался kind='method', получено '{results[0].kind}'"


def test_format_is_method():
    """format должен быть method."""
    idx = build_index()

    results = idx.definition("tiny_pkg.b.Formatter.format")
    assert len(results) == 1
    assert results[0].kind == "method"
    assert results[0].line == 10


def test_formatter_is_class():
    """Formatter должен быть class."""
    idx = build_index()

    results = idx.definition("tiny_pkg.b.Formatter")
    assert len(results) == 1
    assert results[0].kind == "class"
    assert results[0].line == 9
