"""Тесты для unresolved: self во вложенной функции."""

from pathlib import Path

from repo_map.index import RepoIndex

FIXTURE = Path(__file__).parent.parent / "fixtures" / "unresolved" / "unresolved_self_nested"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def test_self_in_nested_function_is_unresolved():
    """self.method() во вложенной функции должен быть unresolved."""
    idx = build_index()
    # Вызов относится к ближайшему охватывающему символу — самой inner_function,
    # а не к outer_method.
    result = idx.callees("unresolved_self_nested.mod.MyClass.outer_method.inner_function")

    # self.inner_method() внутри inner_function должен быть unresolved
    unresolved = result["unresolved"]
    assert len(unresolved) > 0

    self_unresolved = [u for u in unresolved if "self" in u["expression"]]
    assert len(self_unresolved) > 0
    reason = self_unresolved[0]["reason"].lower()
    assert "nested" in reason or "self" in reason

    # и не резолвится во внутренний метод класса
    internal_names = [r.qualified_name for r in result["results"]]
    assert "unresolved_self_nested.mod.MyClass.inner_method" not in internal_names


def test_outer_method_calls_inner_function():
    """Сам outer_method вызывает inner_function — это обычная вложенная функция."""
    idx = build_index()
    result = idx.callees("unresolved_self_nested.mod.MyClass.outer_method")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "unresolved_self_nested.mod.MyClass.outer_method.inner_function" in internal_names
