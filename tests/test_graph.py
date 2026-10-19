"""Тесты для CallGraph."""

from repo_map.graph import CallGraph
from repo_map.model import CallSite


def test_from_call_sites():
    """Граф строится из internal вызовов."""
    call_sites = [
        CallSite(
            expression="run_helper(value)",
            file="tiny_pkg/a.py",
            line=8,
            scope="tiny_pkg.a.public_api",
            resolution="internal",
            target="tiny_pkg.b.helper",
        ),
        CallSite(
            expression="normalize(value)",
            file="tiny_pkg/b.py",
            line=6,
            scope="tiny_pkg.b.helper",
            resolution="internal",
            target="tiny_pkg.b.normalize",
        ),
    ]

    graph = CallGraph.from_call_sites(call_sites)

    # Проверяем рёбра
    assert "tiny_pkg.a.public_api" in graph.callers("tiny_pkg.b.helper")
    assert "tiny_pkg.b.helper" in graph.callers("tiny_pkg.b.normalize")


def test_callers():
    """callers возвращает вызывающих."""
    call_sites = [
        CallSite(
            expression="helper(x)",
            file="a.py",
            line=1,
            scope="mod.func1",
            resolution="internal",
            target="mod.helper",
        ),
        CallSite(
            expression="helper(y)",
            file="a.py",
            line=2,
            scope="mod.func2",
            resolution="internal",
            target="mod.helper",
        ),
    ]

    graph = CallGraph.from_call_sites(call_sites)
    callers = graph.callers("mod.helper")

    assert "mod.func1" in callers
    assert "mod.func2" in callers


def test_callees():
    """callees возвращает вызываемых."""
    call_sites = [
        CallSite(
            expression="helper(x)",
            file="a.py",
            line=1,
            scope="mod.func",
            resolution="internal",
            target="mod.helper",
        ),
        CallSite(
            expression="normalize(x)",
            file="a.py",
            line=2,
            scope="mod.func",
            resolution="internal",
            target="mod.normalize",
        ),
    ]

    graph = CallGraph.from_call_sites(call_sites)
    callees = graph.callees("mod.func")

    assert "mod.helper" in callees
    assert "mod.normalize" in callees


def test_shortest_path():
    """shortest_path находит кратчайший путь."""
    call_sites = [
        CallSite(expression="", file="", line=1, scope="a", resolution="internal", target="b"),
        CallSite(expression="", file="", line=2, scope="b", resolution="internal", target="c"),
        CallSite(expression="", file="", line=3, scope="c", resolution="internal", target="d"),
    ]

    graph = CallGraph.from_call_sites(call_sites)
    path = graph.shortest_path("a", "d")

    assert path == ["a", "b", "c", "d"]


def test_shortest_path_no_path():
    """shortest_path возвращает None, если пути нет."""
    call_sites = [
        CallSite(expression="", file="", line=1, scope="a", resolution="internal", target="b"),
    ]

    graph = CallGraph.from_call_sites(call_sites)
    path = graph.shortest_path("b", "a")  # обратного пути нет

    assert path is None


def test_external_calls_not_in_graph():
    """External вызовы не добавляют рёбра."""
    call_sites = [
        CallSite(
            expression="json.dumps(x)",
            file="a.py",
            line=1,
            scope="mod.func",
            resolution="external",
            target="json.dumps",
        ),
    ]

    graph = CallGraph.from_call_sites(call_sites)
    callees = graph.callees("mod.func")

    assert "json.dumps" not in callees


def test_unresolved_calls_not_in_graph():
    """Unresolved вызовы не добавляют рёбра."""
    call_sites = [
        CallSite(
            expression="formatter.format(x)",
            file="a.py",
            line=1,
            scope="mod.func",
            resolution="unresolved",
            target=None,
            reason="local variable",
        ),
    ]

    graph = CallGraph.from_call_sites(call_sites)
    callees = graph.callees("mod.func")

    assert len(callees) == 0
