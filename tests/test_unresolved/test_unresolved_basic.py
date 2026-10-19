"""Тесты для базовых unresolved-случаев.

Проверяет, что эти вызовы НЕ резолвятся в internal,
а остаются unresolved с правильными причинами.
"""

from pathlib import Path

from repo_map.index import RepoIndex

FIXTURE = Path(__file__).parent.parent / "fixtures" / "unresolved" / "unresolved_basic"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def test_type_inference_is_unresolved():
    """obj.method() должен быть unresolved (type inference)."""
    idx = build_index()
    result = idx.callees("unresolved_basic.mod.use_object")

    # Не должно быть internal вызовов
    internal = result.get("results", [])
    assert len(internal) == 0, (
        f"obj.method() не должен резолвиться в internal, "
        f"но получено: {[r['qualified_name'] for r in internal]}"
    )

    # Должен быть unresolved
    unresolved = result.get("unresolved", [])
    assert len(unresolved) > 0, "Ожидался unresolved для obj.method()"

    method_unresolved = [u for u in unresolved if "method" in u.get("expression", "")]
    assert len(method_unresolved) > 0
    assert (
        "type inference" in method_unresolved[0].get("reason", "").lower()
        or "unknown" in method_unresolved[0].get("reason", "").lower()
    )


def test_dynamic_receiver_is_unresolved():
    """dependant.call(**values) должен быть unresolved (dynamic receiver)."""
    idx = build_index()
    result = idx.callees("unresolved_basic.mod.execute")

    # Не должно быть internal вызовов Dependant.call
    internal = result.get("results", [])
    internal_names = [r["qualified_name"] for r in internal]
    assert "unresolved_basic.mod.Dependant.call" not in internal_names, (
        "dependant.call не должен резолвиться в Dependant.call, "
        "потому что dependant — параметр, а не self"
    )

    # Должен быть unresolved
    unresolved = result.get("unresolved", [])
    call_unresolved = [u for u in unresolved if "call" in u.get("expression", "")]
    assert len(call_unresolved) > 0
    assert (
        "dynamic" in call_unresolved[0].get("reason", "").lower()
        or "parameter" in call_unresolved[0].get("reason", "").lower()
    )


def test_local_variable_is_unresolved():
    """Вызов локальной переменной должен быть unresolved."""
    idx = build_index()
    result = idx.callees("unresolved_basic.mod.use_local")

    # Не должно резолвиться в модульную helper
    internal = result.get("results", [])
    internal_names = [r["qualified_name"] for r in internal]
    assert "unresolved_basic.mod.helper" not in internal_names

    # Должен быть unresolved
    unresolved = result.get("unresolved", [])
    assert len(unresolved) > 0
    helper_unresolved = [u for u in unresolved if "helper" in u.get("expression", "")]
    assert len(helper_unresolved) > 0
    assert "local" in helper_unresolved[0].get("reason", "").lower()


def test_unknown_name_is_unresolved():
    """Вызов несуществующего имени должен быть unresolved."""
    idx = build_index()
    result = idx.callees("unresolved_basic.mod.use_unknown")

    unresolved = result.get("unresolved", [])
    assert len(unresolved) > 0
    unknown_unresolved = [u for u in unresolved if "unknown" in u.get("expression", "")]
    assert len(unknown_unresolved) > 0


def test_chained_methods_are_unresolved():
    """Цепочка obj.foo().bar() должна быть unresolved."""
    idx = build_index()
    result = idx.callees("unresolved_basic.mod.use_chained")

    # Не должно быть internal вызовов
    internal = result.get("results", [])
    assert len(internal) == 0

    # Должны быть unresolved для foo и bar
    unresolved = result.get("unresolved", [])
    assert len(unresolved) >= 2, (
        f"Ожидалось минимум 2 unresolved (foo и bar), получено {len(unresolved)}"
    )


def test_callers_exclude_unresolved():
    """callers для helper не должен включать use_local."""
    idx = build_index()
    callers = idx.callers("unresolved_basic.mod.helper")
    caller_names = [c["qualified_name"] for c in callers]

    assert "unresolved_basic.mod.use_local" not in caller_names, (
        "use_local не должен быть в callers для helper, "
        "потому что helper там перекрыт локальной переменной"
    )
