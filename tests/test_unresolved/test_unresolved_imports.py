"""Тесты для unresolved: imports внутри функций и import *."""

from pathlib import Path

from repo_map.index import RepoIndex

FIXTURE = Path(__file__).parent.parent / "fixtures" / "unresolved" / "unresolved_imports"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def test_import_star_is_unresolved():
    """Вызов имени из import * должен быть unresolved."""
    idx = build_index()
    result = idx.callees("unresolved_imports.mod.use_star")

    unresolved = result.get("unresolved", [])
    assert len(unresolved) > 0


def test_local_import_is_unresolved_or_external():
    """import внутри функции — unresolved или external."""
    idx = build_index()
    result = idx.callees("unresolved_imports.mod.use_local_import")

    # json.dumps — external, но если не резолвим local imports, то unresolved
    unresolved = result.get("unresolved", [])
    external = result.get("external", [])

    # Либо unresolved, либо external
    assert len(unresolved) > 0 or len(external) > 0


def test_local_from_import_is_unresolved_or_external():
    """from ... import внутри функции — unresolved или external."""
    idx = build_index()
    result = idx.callees("unresolved_imports.mod.use_from_local_import")

    unresolved = result.get("unresolved", [])
    external = result.get("external", [])

    assert len(unresolved) > 0 or len(external) > 0
