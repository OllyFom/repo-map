"""Тест для правила 2: вложенная функция.

Проверяет, что:
1. Вложенная функция inner определяется как nested_func.mod.outer.inner
2. Вызов inner() внутри outer резолвится в nested_func.mod.outer.inner
3. Вызов outer() из standalone резолвится в nested_func.mod.outer
"""

from pathlib import Path

from repo_map.index import RepoIndex

# Путь к фикстуре
FIXTURE = Path(__file__).parent / "fixtures" / "nested_func"


def build_index():
    return RepoIndex.build(str(FIXTURE))


# --- Тест 1: определение вложенной функции ---


def test_nested_function_definition():
    """Вложенная функция должна быть в индексе с правильным qualified name."""
    idx = build_index()

    # resolve должен превратить имя в canonical qualified name
    canonical = idx.resolve("nested_func.mod.outer.inner")
    assert canonical == "nested_func.mod.outer.inner", (
        f"Ожидалось nested_func.mod.outer.inner, получено {canonical}"
    )

    # definition должен вернуть символ с kind="function"
    results = idx.definition("nested_func.mod.outer.inner")
    assert len(results) == 1, f"Ожидался 1 результат, получено {len(results)}"

    sym = results[0]
    assert sym.qualified_name == "nested_func.mod.outer.inner"
    assert sym.kind == "function"
    assert sym.file == "nested_func/mod.py"
    assert sym.line == 2


# --- Тест 2: вызов вложенной функции резолвится правильно ---


def test_nested_function_call_resolves():
    """Вызов inner() внутри outer должен резолвиться в outer.inner."""
    idx = build_index()

    # callers для inner должен включать outer
    callers = idx.callers("nested_func.mod.outer.inner")
    caller_names = [c.qualified_name for c in callers]

    assert "nested_func.mod.outer" in caller_names, (
        f"outer должен быть среди callers для inner, но получено: {caller_names}"
    )


# --- Тест 3: callees для outer включает inner ---


def test_outer_callees_include_inner():
    """callees для outer должен включать inner как internal вызов."""
    idx = build_index()

    result = idx.callees("nested_func.mod.outer")

    # Ищем inner среди internal результатов
    internal_names = [r.qualified_name for r in result["results"]]
    assert "nested_func.mod.outer.inner" in internal_names, (
        f"inner должен быть среди callees для outer, но получено: {internal_names}"
    )


# --- Тест 4: outer тоже работает (бонус) ---


def test_standalone_calls_outer():
    """standalone вызывает outer — это обычное правило 1 (same module)."""
    idx = build_index()

    callers = idx.callers("nested_func.mod.outer")
    caller_names = [c.qualified_name for c in callers]

    assert "nested_func.mod.standalone" in caller_names, (
        f"standalone должен быть среди callers для outer, но получено: {caller_names}"
    )
