"""Тест для правила 3: from-import с alias и relative import.

Проверяет, что:
1. from .b import helper as run_helper резолвится в from_alias.b.helper
2. Вызов run_helper() резолвится в from_alias.b.helper
3. from .b import normalize (без alias) тоже работает
"""

from pathlib import Path

from repo_map.index import RepoIndex

# --root — это каталог пакета: его имя становится именем пакета верхнего уровня
FIXTURE = Path(__file__).parent / "fixtures" / "from_alias"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def test_helper_definition():
    """helper в b.py должен быть в индексе."""
    idx = build_index()
    results = idx.definition("from_alias.b.helper")
    assert len(results) == 1
    assert results[0].qualified_name == "from_alias.b.helper"
    assert results[0].kind == "function"
    assert results[0].file == "from_alias/b.py"
    assert results[0].line == 1


def test_normalize_definition():
    """normalize в b.py должен быть в индексе."""
    idx = build_index()
    results = idx.definition("from_alias.b.normalize")
    assert len(results) == 1
    assert results[0].qualified_name == "from_alias.b.normalize"


def test_use_alias_calls_helper():
    """Вызов run_helper() в use_alias должен резолвиться в b.helper."""
    idx = build_index()
    result = idx.callees("from_alias.a.use_alias")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "from_alias.b.helper" in internal_names, (
        f"run_helper должен резолвиться в b.helper, но получено: {internal_names}"
    )


def test_use_direct_calls_normalize():
    """Вызов normalize() в use_direct должен резолвиться в b.normalize."""
    idx = build_index()
    result = idx.callees("from_alias.a.use_direct")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "from_alias.b.normalize" in internal_names


def test_use_both_calls_both():
    """use_both должен вызывать и helper (через alias), и normalize."""
    idx = build_index()
    result = idx.callees("from_alias.a.use_both")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "from_alias.b.helper" in internal_names
    assert "from_alias.b.normalize" in internal_names


def test_callers_of_helper():
    """callers для helper должен включать use_alias и use_both."""
    idx = build_index()
    callers = idx.callers("from_alias.b.helper")
    caller_names = [c.qualified_name for c in callers]

    assert "from_alias.a.use_alias" in caller_names
    assert "from_alias.a.use_both" in caller_names


def test_callers_of_normalize():
    """callers для normalize должен включать use_direct и use_both."""
    idx = build_index()
    callers = idx.callers("from_alias.b.normalize")
    caller_names = [c.qualified_name for c in callers]

    assert "from_alias.a.use_direct" in caller_names
    assert "from_alias.a.use_both" in caller_names


def test_references_include_imports():
    """references для helper должен включать импорт из a.py."""
    idx = build_index()
    refs = idx.references("from_alias.b.helper")

    import_refs = [r for r in refs if r.kind == "import"]
    assert len(import_refs) > 0, "Ожидался хотя бы один import reference"

    import_files = [r.file for r in import_refs]
    assert "from_alias/a.py" in import_files


def test_call_status_is_internal():
    """Вызов run_helper() должен иметь статус internal."""
    idx = build_index()

    helper_calls = [
        cs for cs in idx.call_sites("from_alias.a.use_alias") if cs.target == "from_alias.b.helper"
    ]
    assert len(helper_calls) == 1
    assert helper_calls[0].resolution == "internal"
    assert helper_calls[0].expression == "run_helper"
