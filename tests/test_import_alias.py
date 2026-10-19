"""Тест для правила 5: import с alias модуля.

Проверяет два варианта:
1. import pkg.b as b; b.helper()
2. import pkg.b; pkg.b.helper()

Оба должны резолвиться в pkg.b.helper.

Все три модуля лежат в одном пакете pkg: --root указывает на каталог пакета,
поэтому имя верхнего уровня у всех символов одно (pkg).
"""

from pathlib import Path

from repo_map.index import RepoIndex

FIXTURE = Path(__file__).parent / "fixtures" / "import_alias" / "pkg"


def build_index():
    return RepoIndex.build(str(FIXTURE))


# --- Тест 1: определение helper находится правильно ---


def test_helper_definition():
    """pkg.b.helper должен быть в индексе как функция."""
    idx = build_index()

    results = idx.definition("pkg.b.helper")
    assert len(results) == 1, f"Ожидался 1 результат, получено {len(results)}"

    sym = results[0]
    assert sym.qualified_name == "pkg.b.helper"
    assert sym.kind == "function"
    assert sym.file == "pkg/b.py"
    assert sym.line == 1


# --- Тест 2: вызов через alias (b.helper()) ---


def test_call_via_alias():
    """b.helper() в use_via_alias должен резолвиться в pkg.b.helper."""
    idx = build_index()

    result = idx.callees("pkg.use_alias.use_via_alias")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "pkg.b.helper" in internal_names, (
        f"pkg.b.helper должен быть среди callees для use_via_alias, но получено: {internal_names}"
    )


# --- Тест 3: вызов через полный путь (pkg.b.helper()) ---


def test_call_via_full_path():
    """pkg.b.helper() в use_via_full_path должен резолвиться в pkg.b.helper."""
    idx = build_index()

    result = idx.callees("pkg.use_full.use_via_full_path")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "pkg.b.helper" in internal_names, (
        f"pkg.b.helper должен быть среди callees для use_via_full_path, "
        f"но получено: {internal_names}"
    )


# --- Тест 4: callers для pkg.b.helper включает обе функции ---


def test_callers_include_both():
    """callers для pkg.b.helper должен включать use_via_alias и use_via_full_path."""
    idx = build_index()

    callers = idx.callers("pkg.b.helper")
    caller_names = [c.qualified_name for c in callers]

    assert "pkg.use_alias.use_via_alias" in caller_names, (
        f"use_via_alias должен быть среди callers, но получено: {caller_names}"
    )
    assert "pkg.use_full.use_via_full_path" in caller_names, (
        f"use_via_full_path должен быть среди callers, но получено: {caller_names}"
    )


# --- Тест 5: references ---


def test_references_include_imports_and_calls():
    """Импорты модуля pkg.b (в use_alias.py и use_full.py) и вызовы pkg.b.helper."""
    idx = build_index()

    # `import pkg.b [as b]` импортирует модуль, поэтому import-reference указывает на pkg.b
    import_files = [r.file for r in idx.references("pkg.b") if r.kind == "import"]
    assert "pkg/use_alias.py" in import_files
    assert "pkg/use_full.py" in import_files

    # Вызовы относятся к самой функции
    call_scopes = [r.scope for r in idx.references("pkg.b.helper") if r.kind == "call"]
    assert "pkg.use_alias.use_via_alias" in call_scopes
    assert "pkg.use_full.use_via_full_path" in call_scopes
