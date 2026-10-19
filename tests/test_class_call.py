"""Тест для правила 7: вызов класса.

Проверяет, что:
1. Классы определяются с kind="class"
2. Вызов b.Formatter() резолвится в class_call.b.Formatter (сам класс, не __init__)
3. Вызов b.Processor(name) тоже резолвится в класс
4. callers и references работают корректно для классов
"""

from pathlib import Path

from repo_map.index import RepoIndex

# --root — это каталог пакета: его имя становится именем пакета верхнего уровня
FIXTURE = Path(__file__).parent / "fixtures" / "class_call"


def build_index():
    return RepoIndex.build(str(FIXTURE))


def test_formatter_definition():
    """Formatter должен быть в индексе как класс."""
    idx = build_index()
    results = idx.definition("class_call.b.Formatter")

    assert len(results) == 1
    sym = results[0]
    assert sym.qualified_name == "class_call.b.Formatter"
    assert sym.kind == "class", f"Ожидался kind='class', получено '{sym.kind}'"
    assert sym.file == "class_call/b.py"
    assert sym.line == 1  # строка с "class Formatter:"


def test_processor_definition():
    """Processor должен быть в индексе как класс."""
    idx = build_index()
    results = idx.definition("class_call.b.Processor")

    assert len(results) == 1
    sym = results[0]
    assert sym.qualified_name == "class_call.b.Processor"
    assert sym.kind == "class"
    assert sym.file == "class_call/b.py"
    assert sym.line == 9


def test_create_formatter_calls_formatter_class():
    """Вызов b.Formatter() должен резолвиться в b.Formatter (класс)."""
    idx = build_index()
    result = idx.callees("class_call.a.create_formatter")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "class_call.b.Formatter" in internal_names, (
        f"b.Formatter() должен резолвиться в b.Formatter (класс), но получено: {internal_names}"
    )

    # Проверяем, что это именно класс, а не метод __init__
    formatter_results = [
        r for r in result["results"] if r.qualified_name == "class_call.b.Formatter"
    ]
    assert len(formatter_results) == 1
    assert formatter_results[0].kind == "class"


def test_create_processor_calls_processor_class():
    """Вызов b.Processor(name) должен резолвиться в b.Processor (класс)."""
    idx = build_index()
    result = idx.callees("class_call.a.create_processor")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "class_call.b.Processor" in internal_names


def test_use_classes_calls_both():
    """use_classes должен вызывать и Formatter, и Processor."""
    idx = build_index()
    result = idx.callees("class_call.a.use_classes")

    internal_names = [r.qualified_name for r in result["results"]]
    assert "class_call.b.Formatter" in internal_names
    assert "class_call.b.Processor" in internal_names


def test_callers_of_formatter():
    """callers для Formatter должен включать create_formatter и use_classes."""
    idx = build_index()
    callers = idx.callers("class_call.b.Formatter")
    caller_names = [c.qualified_name for c in callers]

    assert "class_call.a.create_formatter" in caller_names
    assert "class_call.a.use_classes" in caller_names


def test_callers_of_processor():
    """callers для Processor должен включать create_processor и use_classes."""
    idx = build_index()
    callers = idx.callers("class_call.b.Processor")
    caller_names = [c.qualified_name for c in callers]

    assert "class_call.a.create_processor" in caller_names
    assert "class_call.a.use_classes" in caller_names


def test_references_include_imports():
    """a.py делает `from . import b`, поэтому import-reference указывает на модуль b."""
    idx = build_index()
    refs = idx.references("class_call.b")

    import_refs = [r for r in refs if r.kind == "import"]
    assert len(import_refs) > 0, "Ожидался хотя бы один import reference"

    import_files = [r.file for r in import_refs]
    assert "class_call/a.py" in import_files


def test_references_include_calls():
    """references для Formatter должен включать вызовы из a.py."""
    idx = build_index()
    refs = idx.references("class_call.b.Formatter")

    call_refs = [r for r in refs if r.kind == "call"]
    assert len(call_refs) >= 2, (
        f"Ожидалось минимум 2 call reference (create_formatter и use_classes), "
        f"получено {len(call_refs)}"
    )

    call_scopes = [r.scope for r in call_refs]
    assert "class_call.a.create_formatter" in call_scopes
    assert "class_call.a.use_classes" in call_scopes


def test_call_status_is_internal():
    """Вызов b.Formatter() должен иметь статус internal."""
    idx = build_index()

    formatter_calls = [
        cs
        for cs in idx.call_sites("class_call.a.create_formatter")
        if cs.target == "class_call.b.Formatter"
    ]
    assert len(formatter_calls) == 1
    assert formatter_calls[0].resolution == "internal"


def test_class_not_resolved_to_init():
    """Вызов класса должен резолвиться в сам класс, а не в __init__."""
    idx = build_index()
    result = idx.callees("class_call.a.create_processor")

    internal_names = [r.qualified_name for r in result["results"]]

    # Должен быть Processor (класс), а не Processor.__init__
    assert "class_call.b.Processor" in internal_names
    assert not [name for name in internal_names if "__init__" in name]
