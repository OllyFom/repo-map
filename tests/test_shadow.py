"""Тест для правила 9: перекрытие локальным именем.

Проверяет, что вызовы перекрытых имён НЕ резолвятся в функции модуля,
а остаются unresolved с правильной причиной.
"""

from pathlib import Path

from repo_map.index import RepoIndex

# --root — это каталог пакета: его имя становится именем пакета верхнего уровня
FIXTURE = Path(__file__).parent / "fixtures" / "shadow" / "rule9_shadow"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def test_shadow_by_parameter_is_unresolved():
    """Вызов helper() в shadow_by_parameter должен быть unresolved (параметр)."""
    idx = build_index()
    result = idx.callees("rule9_shadow.mod.shadow_by_parameter")

    # Проверяем, что helper НЕ резолвится в модульную функцию
    internal_names = [r.qualified_name for r in result["results"]]
    assert "rule9_shadow.mod.helper" not in internal_names, (
        "helper не должен резолвиться в модульную функцию, потому что он перекрыт параметром"
    )

    # Проверяем, что есть unresolved с правильной причиной
    unresolved = result["unresolved"]
    assert len(unresolved) > 0, "Ожидался хотя бы один unresolved"

    helper_unresolved = [u for u in unresolved if "helper" in u["expression"]]
    assert len(helper_unresolved) > 0, "Ожидался unresolved для helper"
    reason = helper_unresolved[0]["reason"].lower()
    assert "parameter" in reason or "local" in reason


def test_shadow_by_assignment_is_unresolved():
    """Вызов normalize() в shadow_by_assignment должен быть unresolved (переменная)."""
    idx = build_index()
    result = idx.callees("rule9_shadow.mod.shadow_by_assignment")

    # normalize НЕ должен резолвиться в модульную функцию
    internal_names = [r.qualified_name for r in result["results"]]
    assert "rule9_shadow.mod.normalize" not in internal_names, (
        "normalize не должен резолвиться в модульную функцию, "
        "потому что он перекрыт локальной переменной"
    )

    # Проверяем unresolved
    unresolved = result["unresolved"]
    normalize_unresolved = [u for u in unresolved if "normalize" in u["expression"]]
    assert len(normalize_unresolved) > 0, "Ожидался unresolved для normalize"
    assert "local" in normalize_unresolved[0]["reason"].lower()


def test_shadow_imported_is_unresolved():
    """Вызов helper() в shadow_imported должен быть unresolved (локальная лямбда)."""
    idx = build_index()
    result = idx.callees("rule9_shadow.mod.shadow_imported")

    # helper НЕ должен резолвиться в модульную функцию
    internal_names = [r.qualified_name for r in result["results"]]
    assert "rule9_shadow.mod.helper" not in internal_names

    # Проверяем unresolved
    assert len(result["unresolved"]) > 0


def test_normal_call_still_works():
    """Обычный вызов helper() в normal_call должен резолвиться нормально."""
    idx = build_index()
    result = idx.callees("rule9_shadow.mod.normal_call")

    # helper должен резолвиться в модульную функцию
    internal_names = [r.qualified_name for r in result["results"]]
    assert "rule9_shadow.mod.helper" in internal_names, (
        "В normal_call helper должен резолвиться нормально, потому что он не перекрыт"
    )


def test_callers_of_helper_excludes_shadowed():
    """callers для helper НЕ должен включать функции с перекрытием."""
    idx = build_index()
    callers = idx.callers("rule9_shadow.mod.helper")
    caller_names = [c.qualified_name for c in callers]

    # normal_call должен быть среди callers
    assert "rule9_shadow.mod.normal_call" in caller_names

    # shadow_by_parameter и shadow_imported НЕ должны быть
    assert "rule9_shadow.mod.shadow_by_parameter" not in caller_names, (
        "shadow_by_parameter не должен быть в callers, потому что helper там перекрыт параметром"
    )
    assert "rule9_shadow.mod.shadow_imported" not in caller_names


def test_callers_of_normalize_excludes_shadowed():
    """callers для normalize НЕ должен включать shadow_by_assignment."""
    idx = build_index()
    callers = idx.callers("rule9_shadow.mod.normalize")
    caller_names = [c.qualified_name for c in callers]

    assert "rule9_shadow.mod.shadow_by_assignment" not in caller_names, (
        "shadow_by_assignment не должен быть в callers, "
        "потому что normalize там перекрыт локальной переменной"
    )


def test_references_exclude_shadowed_calls():
    """references для helper не должен включать вызовы из перекрытых функций."""
    idx = build_index()
    refs = idx.references("rule9_shadow.mod.helper")
    call_refs = [r for r in refs if r.kind == "call"]

    scopes = [r.scope for r in call_refs]

    # normal_call должен быть
    assert "rule9_shadow.mod.normal_call" in scopes

    # shadow_by_parameter и shadow_imported НЕ должны быть
    assert "rule9_shadow.mod.shadow_by_parameter" not in scopes
    assert "rule9_shadow.mod.shadow_imported" not in scopes
