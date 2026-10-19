"""Тест для правила 4: import модуля и вызов его атрибутов.

Проверяет, что:
1. from . import b импортирует модуль b
2. b.helper() резолвится в from_module.b.helper
3. b.Formatter() резолвится в from_module.b.Formatter
"""

from pathlib import Path

from repo_map.index import RepoIndex

# --root — это каталог пакета: его имя становится именем пакета верхнего уровня
FIXTURE = Path(__file__).parent / "fixtures" / "from_module"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def test_helper_definition():
    """helper в b.py должен быть в индексе."""
    idx = build_index()
    results = idx.definition("from_module.b.helper")
    assert len(results) == 1
    assert results[0].qualified_name == "from_module.b.helper"
    assert results[0].file == "from_module/b.py"


def test_formatter_definition():
    """Formatter в b.py должен быть в индексе."""
    idx = build_index()
    results = idx.definition("from_module.b.Formatter")
    assert len(results) == 1
    assert results[0].qualified_name == "from_module.b.Formatter"
    assert results[0].kind == "class"


def test_use_module_function_calls_helper():
    """Вызов b.helper() в use_module_function должен резолвиться в b.helper."""
    idx = build_index()
    result = idx.callees("from_module.a.use_module_function")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "from_module.b.helper" in internal_names, (
        f"b.helper должен резолвиться в b.helper, но получено: {internal_names}"
    )


def test_use_module_class_calls_formatter():
    """Вызов b.Formatter() в use_module_class должен резолвиться в b.Formatter."""
    idx = build_index()
    result = idx.callees("from_module.a.use_module_class")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "from_module.b.Formatter" in internal_names, (
        f"b.Formatter должен резолвиться в b.Formatter, но получено: {internal_names}"
    )


def test_use_both_calls_both():
    """use_both должен вызывать и b.helper, и b.Formatter."""
    idx = build_index()
    result = idx.callees("from_module.a.use_both")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "from_module.b.helper" in internal_names
    assert "from_module.b.Formatter" in internal_names


def test_callers_of_helper():
    """callers для helper должен включать use_module_function и use_both."""
    idx = build_index()
    callers = idx.callers("from_module.b.helper")
    caller_names = [c.qualified_name for c in callers]

    assert "from_module.a.use_module_function" in caller_names
    assert "from_module.a.use_both" in caller_names


def test_callers_of_formatter():
    """callers для Formatter должен включать use_module_class и use_both."""
    idx = build_index()
    callers = idx.callers("from_module.b.Formatter")
    caller_names = [c.qualified_name for c in callers]

    assert "from_module.a.use_module_class" in caller_names
    assert "from_module.a.use_both" in caller_names


def test_references_include_imports():
    """`from . import b` — это import модуля b, а не helper: reference указывает на модуль."""
    idx = build_index()
    refs = idx.references("from_module.b")

    import_refs = [r for r in refs if r.kind == "import"]
    assert len(import_refs) > 0, "Ожидался хотя бы один import reference"

    import_files = [r.file for r in import_refs]
    assert "from_module/a.py" in import_files


def test_fmt_format_is_unresolved():
    """Вызов fmt.format() должен быть unresolved (локальная переменная)."""
    idx = build_index()
    result = idx.callees("from_module.a.use_module_class")

    # fmt.format() не должен резолвиться в Formatter.format
    internal_names = [r.qualified_name for r in result["results"]]
    assert "from_module.b.Formatter.format" not in internal_names, (
        "fmt.format не должен резолвиться, потому что fmt — локальная переменная"
    )

    # Должен быть unresolved
    format_unresolved = [u for u in result["unresolved"] if "format" in u["expression"]]
    assert len(format_unresolved) > 0, "Ожидался unresolved для fmt.format"
