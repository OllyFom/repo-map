"""Scope вызовов и строки определений: декораторы и тело класса.

Из задания:
- scope вызова — ближайший охватывающий символ: функция/метод, иначе класс, иначе модуль;
- декоратор вычисляется в охватывающей области;
- для определения line — строка с def/class, а не строка декоратора.
"""

from pathlib import Path

from repo_map.index import RepoIndex

FIXTURE = Path(__file__).parent / "fixtures" / "scope_rules"
PKG = "scope_rules"
MOD = f"{PKG}.mod"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def targets(idx, scope):
    return [cs.target for cs in idx.call_sites(scope) if cs.resolution == "internal"]


def test_definition_line_is_def_not_decorator():
    idx = build_index()
    # @make_decorator("x") на строке 9, def decorated() на строке 10
    sym = idx.definition(f"{MOD}.decorated")[0]
    assert sym.kind == "function"
    assert sym.line == 10

    # @make_decorator("y") на строке 17, def method на строке 18
    method = idx.definition(f"{MOD}.Holder.method")[0]
    assert method.kind == "method"
    assert method.line == 18


def test_decorator_call_belongs_to_enclosing_scope():
    """make_decorator("x") вычисляется на уровне модуля, а не внутри decorated."""
    idx = build_index()

    assert f"{MOD}.make_decorator" in targets(idx, MOD)
    assert f"{MOD}.make_decorator" not in targets(idx, f"{MOD}.decorated")
    assert targets(idx, f"{MOD}.decorated") == [f"{MOD}.helper"]


def test_method_decorator_call_belongs_to_class_scope():
    """Декоратор метода вычисляется в теле класса: scope — Holder."""
    idx = build_index()

    assert f"{MOD}.make_decorator" in targets(idx, f"{MOD}.Holder")
    assert f"{MOD}.make_decorator" not in targets(idx, f"{MOD}.Holder.method")
    assert targets(idx, f"{MOD}.Holder.method") == [f"{MOD}.helper"]


def test_class_body_call_belongs_to_class():
    """value = helper() в теле класса: scope — Holder, а не модуль и не метод."""
    idx = build_index()

    assert f"{MOD}.helper" in targets(idx, f"{MOD}.Holder")
    assert f"{MOD}.helper" not in targets(idx, MOD)


def test_class_and_module_as_callers():
    """callers может вернуть класс или модуль, если вызов стоит в их теле."""
    idx = build_index()

    kinds = {c.qualified_name: c.kind for c in idx.callers(f"{MOD}.make_decorator")}
    assert kinds[MOD] == "module"
    assert kinds[f"{MOD}.Holder"] == "class"

    helper_callers = {c.qualified_name: c.kind for c in idx.callers(f"{MOD}.helper")}
    assert helper_callers[f"{MOD}.Holder"] == "class"
    assert helper_callers[f"{MOD}.decorated"] == "function"
    assert helper_callers[f"{MOD}.Holder.method"] == "method"
