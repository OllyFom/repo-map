"""Тесты для unresolved: getattr, monkey patching, динамические импорты, import *.

Главное — отсутствие ложных рёбер: цель нельзя установить по поддержанным правилам,
значит, вызов не должен превращаться в уверенное internal-ребро.
"""

from pathlib import Path

from repo_map.index import RepoIndex

FIXTURE = Path(__file__).parent.parent / "fixtures" / "unresolved" / "unresolved_dynamic"
PKG = "unresolved_dynamic"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def internal_names(result):
    return [r.qualified_name for r in result["results"]]


def unresolved_expressions(result):
    return [u["expression"] for u in result["unresolved"]]


def test_definitions_exist():
    idx = build_index()
    for qn in [f"{PKG}.mod.helper", f"{PKG}.mod.Target.method", f"{PKG}.star_source.star_func"]:
        assert len(idx.definition(qn)) == 1, qn


def test_getattr_call_is_unresolved():
    """getattr(obj, "helper")() не должен превращаться в вызов helper."""
    idx = build_index()
    result = idx.callees(f"{PKG}.mod.use_getattr")

    assert f"{PKG}.mod.helper" not in internal_names(result)
    assert any(e.startswith("getattr(") for e in unresolved_expressions(result)), (
        f"Ожидался unresolved для getattr(...)(), получено: {unresolved_expressions(result)}"
    )
    assert idx.callers(f"{PKG}.mod.helper") == []


def test_monkey_patching_is_not_followed():
    """После setattr(Target, "method", replacement) вызов Target().method() не угадываем."""
    idx = build_index()
    result = idx.callees(f"{PKG}.mod.use_setattr_patch")

    names = internal_names(result)
    assert f"{PKG}.mod.Target.method" not in names
    assert f"{PKG}.mod.replacement" not in names
    assert "Target().method" in unresolved_expressions(result)

    # сам вызов класса Target() при этом честный internal
    assert f"{PKG}.mod.Target" in names

    # ни method, ни replacement не получают ложных callers
    assert idx.callers(f"{PKG}.mod.Target.method") == []
    assert idx.callers(f"{PKG}.mod.replacement") == []


def test_star_import_name_is_not_guessed():
    """from .star_source import * не создаёт ложных рёбер.

    Имя star_func берётся из import *, который не поддерживается: допустим unresolved,
    допустим и корректный internal, но не external и не чужая цель.
    """
    idx = build_index()
    result = idx.callees(f"{PKG}.mod.use_star_name")

    assert result["external"] == []
    names = internal_names(result)
    if names:
        assert names == [f"{PKG}.star_source.star_func"]
    else:
        assert "star_func" in unresolved_expressions(result)


def test_import_module_call_is_unresolved():
    """importlib.import_module(...).star_func() — динамический импорт."""
    idx = build_index()
    result = idx.callees(f"{PKG}.mod.use_import_module")

    assert f"{PKG}.star_source.star_func" not in internal_names(result)
    assert any(
        "import_module" in e and e.endswith("star_func") for e in unresolved_expressions(result)
    )

    # сам importlib.import_module — честный external
    externals = {e["target"] for e in result["external"]}
    assert "importlib.import_module" in externals


def test_dunder_import_call_is_unresolved():
    """__import__(...).star_func() — динамический импорт."""
    idx = build_index()
    result = idx.callees(f"{PKG}.mod.use_dunder_import")

    assert f"{PKG}.star_source.star_func" not in internal_names(result)
    assert any(e.startswith("__import__(") for e in unresolved_expressions(result))


def test_no_edges_to_dynamic_targets_in_graph():
    idx = build_index()

    assert idx.path(f"{PKG}.mod.use_getattr", f"{PKG}.mod.helper") is None
    assert idx.path(f"{PKG}.mod.use_import_module", f"{PKG}.star_source.star_func") is None
    assert idx.path(f"{PKG}.mod.use_dunder_import", f"{PKG}.star_source.star_func") is None
