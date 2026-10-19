"""Тест для правила 1: имя из того же модуля."""

from pathlib import Path

from repo_map.index import RepoIndex

FIXTURE = Path(__file__).parent / "fixtures" / "same_module"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def test_definitions_exist():
    """Все функции должны быть в индексе с правильным qualified name."""
    idx = build_index()

    for name in ["helper", "normalize", "use_helper", "use_normalize", "use_both"]:
        qn = f"same_module.mod.{name}"
        results = idx.definition(qn)
        assert len(results) == 1, f"Ожидался 1 результат для {qn}"
        assert results[0].qualified_name == qn
        assert results[0].kind == "function"
        assert results[0].file == "same_module/mod.py"


def test_use_helper_calls_helper():
    """Вызов helper() в use_helper должен резолвиться в helper."""
    idx = build_index()
    result = idx.callees("same_module.mod.use_helper")

    internal_names = [r.qualified_name for r in result.get("results", [])]
    assert "same_module.mod.helper" in internal_names


def test_use_normalize_calls_normalize():
    """Вызов normalize() в use_normalize должен резолвиться в normalize."""
    idx = build_index()
    result = idx.callees("same_module.mod.use_normalize")

    internal_names = [r.qualified_name for r in result.get("results", [])]
    assert "same_module.mod.normalize" in internal_names


def test_use_both_calls_both():
    """use_both должен вызывать и helper, и normalize."""
    idx = build_index()
    result = idx.callees("same_module.mod.use_both")

    internal_names = [r.qualified_name for r in result.get("results", [])]
    assert "same_module.mod.helper" in internal_names
    assert "same_module.mod.normalize" in internal_names


def test_callers_of_helper():
    """callers для helper должен включать use_helper и use_both."""
    idx = build_index()
    callers = idx.callers("same_module.mod.helper")
    caller_names = [c.qualified_name for c in callers]

    assert "same_module.mod.use_helper" in caller_names, (
        f"use_helper должен быть среди callers для helper, но получено: {caller_names}"
    )
    assert "same_module.mod.use_both" in caller_names


def test_callers_of_normalize():
    """callers для normalize должен включать use_normalize и use_both."""
    idx = build_index()
    callers = idx.callers("same_module.mod.normalize")
    caller_names = [c.qualified_name for c in callers]

    assert "same_module.mod.use_normalize" in caller_names
    assert "same_module.mod.use_both" in caller_names


def test_references_of_helper():
    """references для helper должен включать вызовы из use_helper и use_both."""
    idx = build_index()
    refs = idx.references("same_module.mod.helper")
    call_refs = [r for r in refs if r.kind == "call"]

    scopes = [r.scope for r in call_refs]
    assert "same_module.mod.use_helper" in scopes, (
        f"use_helper должен быть среди scope в references, но получено: {scopes}"
    )
    assert "same_module.mod.use_both" in scopes


def test_call_status_is_internal():
    """Вызов helper() из use_helper должен иметь статус internal."""
    idx = build_index()
    result = idx.callees("same_module.mod.use_helper")

    helper_calls = [
        r for r in result.get("results", []) if r.qualified_name == "same_module.mod.helper"
    ]
    assert len(helper_calls) == 1
