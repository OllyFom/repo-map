"""Тест для правила re-export через __init__.py.

Проверяет, что:
1. tiny_pkg.public_api резолвится в tiny_pkg.a.public_api
2. definition возвращает правильное определение
3. Re-export работает через __init__.py
"""

from pathlib import Path

from repo_map.index import RepoIndex

FIXTURE = Path(__file__).parent / "fixtures" / "tiny_pkg"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def test_reexport_resolve():
    """tiny_pkg.public_api должен резолвиться в tiny_pkg.a.public_api."""
    idx = build_index()

    canonical = idx.resolve("tiny_pkg.public_api")
    assert canonical == "tiny_pkg.a.public_api", (
        f"Ожидалось tiny_pkg.a.public_api, получено {canonical}"
    )


def test_unknown_symbol_resolves_to_none():
    idx = build_index()
    assert idx.resolve("tiny_pkg.nope") is None
    assert idx.resolve("other.thing") is None


def test_reexport_definition():
    """definition для tiny_pkg.public_api должен вернуть определение из a.py."""
    idx = build_index()

    results = idx.definition("tiny_pkg.public_api")
    assert len(results) == 1, f"Ожидался 1 результат, получено {len(results)}"

    sym = results[0]
    assert sym.qualified_name == "tiny_pkg.a.public_api"
    assert sym.kind == "function"
    assert sym.file == "tiny_pkg/a.py"
    assert sym.line == 7


def test_reexport_callers_by_either_name():
    """callers работает и по canonical имени, и по re-export имени."""
    idx = build_index()

    assert isinstance(idx.callers("tiny_pkg.a.public_api"), list)
    assert idx.callers("tiny_pkg.public_api") == idx.callers("tiny_pkg.a.public_api")


def test_reexport_references():
    """references для tiny_pkg.a.public_api должен включать импорт в __init__.py."""
    idx = build_index()

    refs = idx.references("tiny_pkg.a.public_api")

    import_refs = [r for r in refs if r.kind == "import"]
    assert len(import_refs) > 0, "Ожидался хотя бы один import reference"

    import_files = [r.file for r in import_refs]
    assert "tiny_pkg/__init__.py" in import_files, (
        f"Ожидался импорт в __init__.py, получено: {import_files}"
    )


def test_reexport_module_definition():
    """Сам модуль tiny_pkg должен быть в индексе."""
    idx = build_index()

    results = idx.definition("tiny_pkg")
    assert len(results) == 1
    assert results[0].qualified_name == "tiny_pkg"
    assert results[0].kind == "module"
    assert results[0].file == "tiny_pkg/__init__.py"
    assert results[0].line == 1
