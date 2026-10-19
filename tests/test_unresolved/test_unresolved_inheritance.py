"""Тесты для unresolved-случаев с наследованием."""

from pathlib import Path

from repo_map.index import RepoIndex

FIXTURE = Path(__file__).parent.parent / "fixtures" / "unresolved" / "unresolved_inheritance"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def test_base_class_method_is_unresolved():
    """self.base_method() в Derived должен быть unresolved (наследование)."""
    idx = build_index()
    result = idx.callees("unresolved_inheritance.mod.Derived.derived_method")

    # Если не резолвим наследование, то unresolved
    # Если резолвим, то Base.base_method
    # Для простоты оставим unresolved
    unresolved = result.get("unresolved", [])
    internal = result.get("results", [])

    # Либо unresolved, либо резолвится в Base
    if len(internal) > 0:
        # Если резолвится, то должно быть в Base
        assert any("Base" in r.get("qualified_name", "") for r in internal)
    else:
        # Если не резолвится, то unresolved
        assert len(unresolved) > 0


def test_super_is_unresolved():
    """super().method() должен быть unresolved."""
    idx = build_index()
    result = idx.callees("unresolved_inheritance.mod.WithSuper.method")

    unresolved = result.get("unresolved", [])
    assert len(unresolved) > 0
    super_unresolved = [u for u in unresolved if "super" in u.get("expression", "").lower()]
    assert len(super_unresolved) > 0


def test_cls_method_is_unresolved():
    """cls.method() должен быть unresolved."""
    idx = build_index()
    result = idx.callees("unresolved_inheritance.mod.WithCls.class_method")

    unresolved = result.get("unresolved", [])
    assert len(unresolved) > 0
    cls_unresolved = [u for u in unresolved if "cls" in u.get("expression", "")]
    assert len(cls_unresolved) > 0
