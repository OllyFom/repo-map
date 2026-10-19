"""Repository index: symbols, imports, call sites, references."""

import builtins
import sys
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from repo_map.graph import CallGraph
from repo_map.model import CallSite, Import, Reference, Symbol
from repo_map.parser import parse_file


def iter_python_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root).parts
        if any(part.startswith(".") or part == "__pycache__" for part in parts):
            continue
        yield path


def module_name(root: Path, path: Path) -> str:
    parts = [root.name, *path.relative_to(root).with_suffix("").parts]
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def relative_file(root: Path, path: Path) -> str:
    return path.relative_to(root.parent).as_posix()


def _text(node) -> str:
    """Безопасно достать текст узла."""
    return node.text.decode("utf-8") if node is not None else ""


def _is_async(node) -> bool:
    return any(c.type == "async" for c in node.children)


# Узлы, внутри которых не бывает определений (ускоряет обход определений и локальных имён).
_NO_DEFS_INSIDE = {
    "expression_statement",
    "return_statement",
    "assignment",
    "augmented_assignment",
    "raise_statement",
    "assert_statement",
    "delete_statement",
    "import_statement",
    "import_from_statement",
    "global_statement",
    "nonlocal_statement",
    "pass_statement",
    "break_statement",
    "continue_statement",
    "string",
    "comment",
}

_CALLABLE_KINDS = ("function", "method", "class")


@dataclass
class _Frame:
    """Лексическая область при обходе вызовов."""

    qn: str
    kind: str  # module | class | function | lambda
    locals: set[str] = field(default_factory=set)
    self_name: str | None = None  # имя первого параметра метода
    class_qn: str | None = None  # класс, если это метод


def _pattern_names(node, out: list[str]) -> None:
    """Имена, связываемые целью присваивания / параметром."""
    if node is None:
        return
    if node.type == "identifier":
        out.append(_text(node))
    elif node.type in ("attribute", "subscript", "call"):
        return
    else:
        for child in node.named_children:
            _pattern_names(child, out)


def _parameters(params) -> tuple[list[str], str | None]:
    """Имена параметров и имя первого параметра, если он обычный (identifier)."""
    names: list[str] = []
    first_plain: str | None = None
    if params is None:
        return names, None
    for i, p in enumerate(params.named_children):
        t = p.type
        if t == "identifier":
            names.append(_text(p))
            if i == 0:
                first_plain = _text(p)
        elif t in ("default_parameter", "typed_default_parameter"):
            _pattern_names(p.child_by_field_name("name"), names)
        elif t == "typed_parameter":
            if p.named_children:
                before = len(names)
                _pattern_names(p.named_children[0], names)
                if i == 0 and p.named_children[0].type == "identifier" and len(names) > before:
                    first_plain = names[before]
        elif t in ("list_splat_pattern", "dictionary_splat_pattern"):
            _pattern_names(p, names)
    return names, first_plain


def _import_local_names(node) -> list[str]:
    names = []
    for n in node.children_by_field_name("name"):
        if n.type == "aliased_import":
            names.append(_text(n.child_by_field_name("alias")))
        elif node.type == "import_statement":
            names.append(_text(n).split(".")[0])
        else:
            names.append(_text(n))
    return names


def _walk_locals(node, out: set[str]) -> None:
    """Имена, связываемые в теле функции (без захода во вложенные def/class)."""
    for c in node.named_children:
        t = c.type
        if t in ("function_definition", "class_definition"):
            out.add(_text(c.child_by_field_name("name")))
            continue
        if t == "decorated_definition":
            d = c.child_by_field_name("definition")
            if d is not None:
                out.add(_text(d.child_by_field_name("name")))
            continue
        names: list[str] = []
        if (
            t == "assignment"
            or t == "augmented_assignment"
            or t in ("for_statement", "for_in_clause")
        ):
            _pattern_names(c.child_by_field_name("left"), names)
        elif t == "as_pattern":
            _pattern_names(c.child_by_field_name("alias"), names)
        elif t == "named_expression":
            _pattern_names(c.child_by_field_name("name"), names)
        elif t in ("import_statement", "import_from_statement"):
            names.extend(_import_local_names(c))
        elif t == "except_clause":
            kids = c.named_children
            if len(kids) >= 2 and kids[1].type == "identifier":
                names.append(_text(kids[1]))
        elif t == "lambda":
            # параметры лямбды учитываем консервативно как локальные имена
            names.extend(_parameters(c.child_by_field_name("parameters"))[0])
        out.update(names)
        # присваивания лежат внутри expression_statement, поэтому заходим всюду
        _walk_locals(c, out)


def _attr_chain(node) -> list[str] | None:
    """a.b.c -> ["a", "b", "c"]; None, если база не простое имя."""
    if node.type == "identifier":
        return [_text(node)]
    if node.type == "attribute":
        base = _attr_chain(node.child_by_field_name("object"))
        attr = node.child_by_field_name("attribute")
        if base is None or attr is None:
            return None
        return [*base, _text(attr)]
    return None


class RepoIndex:
    def __init__(self):
        self.root: Path | None = None
        # Все символы проекта: qualified_name -> Symbol (первое определение)
        self.symbols: dict[str, Symbol] = {}
        # Все определения (имя может быть определено несколько раз: if/else, try/except)
        self.defs: dict[str, list[Symbol]] = defaultdict(list)
        self.all_imports: list[Import] = []
        # (import, абсолютное имя цели) — для references
        self._import_targets: list[tuple[Import, str]] = []
        self.all_call_sites: list[CallSite] = []
        self.all_references: list[Reference] = []
        self.graph: CallGraph | None = None
        # module_qn -> {local_name: (kind, dotted_target)}; только импорты верхнего уровня
        self.bindings: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)

    @classmethod
    def build(cls, root: str | Path) -> "RepoIndex":
        """Главный метод: строит индекс по всем файлам."""
        # Глубокие выражения в сгенерированном коде могут давать глубокую рекурсию
        sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))

        root = Path(root).resolve()
        instance = cls()
        instance.root = root
        files = list(iter_python_files(root))

        for py_file in files:
            instance._collect_definitions(py_file)
        for py_file in files:
            instance._collect_imports(py_file)
        # Вызовы разрешаются сразу при обходе: нужен контекст локальных имён
        for py_file in files:
            instance._collect_calls(py_file)

        instance.graph = CallGraph.from_call_sites(instance.all_call_sites)
        instance._build_references()
        return instance

    # ============================================================
    # ЭТАП 1: ОПРЕДЕЛЕНИЯ
    # ============================================================

    def _add_symbol(self, sym: Symbol) -> None:
        self.symbols.setdefault(sym.qualified_name, sym)
        self.defs[sym.qualified_name].append(sym)

    def _collect_definitions(self, py_file: Path):
        tree = parse_file(py_file)
        mod_qn = module_name(self.root, py_file)
        file_rel = relative_file(self.root, py_file)
        self._add_symbol(Symbol(mod_qn, "module", file_rel, 1, False))
        self._walk_defs(tree.root_node, mod_qn, file_rel, parent_is_class=False)

    def _walk_defs(self, node, parent_qn: str, file_rel: str, parent_is_class: bool):
        for child in node.named_children:
            t = child.type
            if t == "class_definition":
                self._add_class(child, parent_qn, file_rel)
            elif t == "function_definition":
                self._add_function(child, parent_qn, file_rel, parent_is_class)
            elif t == "decorated_definition":
                inner = child.child_by_field_name("definition")
                if inner is None:
                    continue
                if inner.type == "class_definition":
                    self._add_class(inner, parent_qn, file_rel)
                elif inner.type == "function_definition":
                    self._add_function(inner, parent_qn, file_rel, parent_is_class)
            elif t not in _NO_DEFS_INSIDE:
                # if / try / with / for / block ... — определения могут лежать внутри
                self._walk_defs(child, parent_qn, file_rel, parent_is_class)

    def _add_class(self, node, parent_qn: str, file_rel: str):
        name = _text(node.child_by_field_name("name"))
        qn = f"{parent_qn}.{name}"
        self._add_symbol(Symbol(qn, "class", file_rel, node.start_point[0] + 1, False))
        body = node.child_by_field_name("body")
        if body is not None:
            self._walk_defs(body, qn, file_rel, parent_is_class=True)

    def _add_function(self, node, parent_qn: str, file_rel: str, parent_is_class: bool):
        name = _text(node.child_by_field_name("name"))
        qn = f"{parent_qn}.{name}"
        kind = "method" if parent_is_class else "function"
        self._add_symbol(Symbol(qn, kind, file_rel, node.start_point[0] + 1, _is_async(node)))
        body = node.child_by_field_name("body")
        if body is not None:
            self._walk_defs(body, qn, file_rel, parent_is_class=False)

    # ============================================================
    # ЭТАП 2: ИМПОРТЫ (только верхний уровень модуля, включая if/try)
    # ============================================================

    def _collect_imports(self, py_file: Path):
        tree = parse_file(py_file)
        mod_qn = module_name(self.root, py_file)
        file_rel = relative_file(self.root, py_file)
        is_init = py_file.name == "__init__.py"
        self._walk_imports(tree.root_node, mod_qn, file_rel, is_init)

    def _walk_imports(self, node, mod_qn: str, file_rel: str, is_init: bool):
        for child in node.named_children:
            t = child.type
            if t == "import_statement":
                self._handle_import_stmt(child, file_rel, mod_qn)
            elif t == "import_from_statement":
                self._handle_import_from(child, mod_qn, file_rel, is_init)
            elif t in ("function_definition", "class_definition", "decorated_definition"):
                # Импорты внутри функций и классов не поддерживаются (имя считается локальным)
                continue
            elif t not in _NO_DEFS_INSIDE:
                self._walk_imports(child, mod_qn, file_rel, is_init)

    def _add_import(self, imp: Import, target: str, binding_kind: str):
        self.all_imports.append(imp)
        self._import_targets.append((imp, target))
        self.bindings[imp.scope][imp.alias] = (binding_kind, target)

    def _handle_import_stmt(self, node, file_rel: str, scope: str):
        """import X / import X.Y / import X.Y as Z / import A, B"""
        line = node.start_point[0] + 1
        for name_node in node.children_by_field_name("name"):
            if name_node.type == "aliased_import":
                module = _text(name_node.child_by_field_name("name"))
                alias = _text(name_node.child_by_field_name("alias"))
                imp = Import(module, None, alias, file_rel, line, scope)
                self._add_import(imp, module, "module")  # b -> pkg.b
            else:
                module = _text(name_node)
                local = module.split(".")[0]
                imp = Import(module, None, local, file_rel, line, scope)
                # "import pkg.b" связывает имя "pkg"; цель ссылки — pkg.b
                self.all_imports.append(imp)
                self._import_targets.append((imp, module))
                self.bindings[scope][local] = ("module", local)

    def _handle_import_from(self, node, mod_qn: str, file_rel: str, is_init: bool):
        """from X import Y / from .X import Y / from . import X / from ..X import Y as Z"""
        line = node.start_point[0] + 1
        module_node = node.child_by_field_name("module_name")
        if module_node is None:
            return

        if module_node.type == "relative_import":
            dots = 0
            dotted = ""
            for c in module_node.children:
                if c.type == "import_prefix":
                    dots = _text(c).count(".")
                elif c.type == "dotted_name":
                    dotted = _text(c)
            parts = mod_qn.split(".")
            # для __init__.py mod_qn — сам пакет, для модуля — пакет это родитель
            pkg_parts = parts if is_init else parts[:-1]
            up = dots - 1
            if up > len(pkg_parts):
                return
            base = pkg_parts[: len(pkg_parts) - up]
            abs_module = ".".join([*base, dotted] if dotted else base)
            original = "." * dots + dotted
        else:
            abs_module = original = _text(module_node)

        for name_node in node.children_by_field_name("name"):
            if name_node.type == "aliased_import":
                orig = _text(name_node.child_by_field_name("name"))
                alias = _text(name_node.child_by_field_name("alias"))
            else:
                orig = alias = _text(name_node)
            target = f"{abs_module}.{orig}" if abs_module else orig
            imp = Import(original, orig, alias, file_rel, line, mod_qn)
            self._add_import(imp, target, "symbol")

    # ============================================================
    # ЭТАП 3: ВЫЗОВЫ (обход с разрешением имён)
    # ============================================================

    def _collect_calls(self, py_file: Path):
        tree = parse_file(py_file)
        mod_qn = module_name(self.root, py_file)
        file_rel = relative_file(self.root, py_file)
        frames = [_Frame(mod_qn, "module")]
        self._visit(tree.root_node, frames, file_rel)

    @staticmethod
    def _scope_qn(frames: list[_Frame]) -> str:
        for f in reversed(frames):
            if f.kind != "lambda":
                return f.qn
        return frames[0].qn

    def _visit(self, node, frames: list[_Frame], file_rel: str):
        t = node.type
        if t == "call":
            self._record_call(node, frames, file_rel)
            for child in node.named_children:
                self._visit(child, frames, file_rel)
        elif t == "function_definition":
            self._visit_function(node, frames, file_rel, decorators=())
        elif t == "class_definition":
            self._visit_class(node, frames, file_rel)
        elif t == "decorated_definition":
            decorators = []
            for child in node.named_children:
                if child.type == "decorator":
                    decorators.append(_text(child).lstrip("@").strip())
                    # декоратор вычисляется в охватывающей области
                    self._visit(child, frames, file_rel)
            inner = node.child_by_field_name("definition")
            if inner is not None and inner.type == "function_definition":
                self._visit_function(inner, frames, file_rel, tuple(decorators))
            elif inner is not None and inner.type == "class_definition":
                self._visit_class(inner, frames, file_rel)
        elif t == "lambda":
            params_node = node.child_by_field_name("parameters")
            if params_node is not None:
                self._visit(params_node, frames, file_rel)  # значения по умолчанию
            names, _ = _parameters(params_node)
            lam = _Frame(self._scope_qn(frames), "lambda", set(names))
            body = node.child_by_field_name("body")
            if body is not None:
                self._visit(body, [*frames, lam], file_rel)
        else:
            for child in node.named_children:
                self._visit(child, frames, file_rel)

    def _visit_function(self, node, frames, file_rel, decorators: tuple[str, ...]):
        parent_qn = self._scope_qn(frames)
        parent = next(f for f in reversed(frames) if f.kind != "lambda")
        qn = f"{parent_qn}.{_text(node.child_by_field_name('name'))}"

        params_node = node.child_by_field_name("parameters")
        # значения по умолчанию и аннотации вычисляются снаружи
        if params_node is not None:
            self._visit(params_node, frames, file_rel)
        ret = node.child_by_field_name("return_type")
        if ret is not None:
            self._visit(ret, frames, file_rel)

        param_names, first_plain = _parameters(params_node)
        assigned: set[str] = set()
        body = node.child_by_field_name("body")
        if body is not None:
            _walk_locals(body, assigned)

        frame = _Frame(qn, "function", set(param_names) | assigned)
        is_static = any(d in ("staticmethod", "classmethod") for d in decorators)
        # self — первый параметр метода, не переприсвоенный в теле
        if parent.kind == "class" and first_plain and not is_static and first_plain not in assigned:
            frame.self_name = first_plain
            frame.class_qn = parent.qn
        if body is not None:
            self._visit(body, [*frames, frame], file_rel)

    def _visit_class(self, node, frames, file_rel):
        qn = f"{self._scope_qn(frames)}.{_text(node.child_by_field_name('name'))}"
        supers = node.child_by_field_name("superclasses")
        if supers is not None:
            self._visit(supers, frames, file_rel)
        body = node.child_by_field_name("body")
        if body is not None:
            self._visit(body, [*frames, _Frame(qn, "class")], file_rel)

    def _record_call(self, node, frames, file_rel: str):
        func_node = node.child_by_field_name("function")
        if func_node is None:
            return
        resolution, target, reason = self._resolve_callee(func_node, frames)
        self.all_call_sites.append(
            CallSite(
                expression=_text(func_node),
                file=file_rel,
                line=node.start_point[0] + 1,
                scope=self._scope_qn(frames),
                resolution=resolution,
                target=target,
                reason=reason,
            )
        )

    # ============================================================
    # ЭТАП 4: РАЗРЕШЕНИЕ ИМЁН
    # ============================================================

    def _lookup_name(self, name: str, frames: list[_Frame]):
        """-> ("local", frame) | ("symbol", qn) | ("dotted", target) | None"""
        for frame in reversed(frames):
            if frame.kind in ("function", "lambda") and name in frame.locals:
                if frame.kind == "function":
                    nested = f"{frame.qn}.{name}"
                    sym = self.symbols.get(nested)
                    if sym is not None and sym.kind in ("function", "class"):
                        return ("symbol", nested)
                return ("local", frame)
        mod = frames[0].qn
        cand = f"{mod}.{name}"
        if cand in self.symbols:
            return ("symbol", cand)
        binding = self.bindings.get(mod, {}).get(name)
        if binding:
            return ("dotted", binding[1])
        return None

    def _is_internal_name(self, dotted: str) -> bool:
        return dotted.split(".")[0] == self.root.name

    def _resolve_callee(self, func_node, frames):
        """-> (resolution, target, reason)"""
        chain = _attr_chain(func_node)
        if chain is None:
            return ("unresolved", None, "dynamic receiver")
        base, rest = chain[0], chain[1:]

        found = self._lookup_name(base, frames)
        if found is None:
            if not rest and hasattr(builtins, base):
                return ("external", f"builtins.{base}", None)
            return ("unresolved", None, "unknown name")

        kind, value = found
        if kind == "local":
            return self._resolve_local(base, rest, value, frames)

        dotted = ".".join([value, *rest])
        canonical = self._canonical(dotted)
        if canonical is not None:
            if self.symbols[canonical].kind in _CALLABLE_KINDS:
                return ("internal", canonical, None)
            return ("unresolved", None, "not callable")
        if self._is_internal_name(dotted):
            return ("unresolved", None, "dynamic receiver" if rest else "unknown name")
        return ("external", dotted, None)

    def _resolve_local(self, base: str, rest: list[str], frame: _Frame, frames):
        """Имя связано локально: параметр, присваивание. Разрешаем только self.method()."""
        current = next(f for f in reversed(frames) if f.kind != "lambda")
        if rest and frame is current and frame.self_name == base and frame.class_qn:
            if len(rest) != 1:
                return ("unresolved", None, "dynamic receiver")
            target = f"{frame.class_qn}.{rest[0]}"
            sym = self.symbols.get(target)
            if sym is not None and sym.kind == "method":
                return ("internal", target, None)
            return ("unresolved", None, "not defined in class")
        if rest and frame.self_name == base and frame is not current:
            # self из охватывающего метода, но вызов внутри вложенной функции
            return ("unresolved", None, "self in nested function")
        if rest:
            # obj.method(): тип obj неизвестен, type inference не поддерживается
            return ("unresolved", None, "local variable (dynamic receiver, no type inference)")
        return ("unresolved", None, "local variable")

    def _canonical(self, qn: str, _seen: set[str] | None = None) -> str | None:
        """Имя по месту определения: раскручивает импорты и re-export (в том числе цепочкой)."""
        if qn in self.symbols:
            return qn
        if "." not in qn:
            return None
        seen = _seen if _seen is not None else set()
        if qn in seen:
            return None
        seen.add(qn)
        prefix, attr = qn.rsplit(".", 1)
        cp = self._canonical(prefix, seen)
        if cp is None:
            return None
        cand = f"{cp}.{attr}"
        if cand in self.symbols:
            return cand
        if self.symbols[cp].kind == "module":
            binding = self.bindings.get(cp, {}).get(attr)
            if binding:
                return self._canonical(binding[1], seen)
        return None

    # ============================================================
    # ЭТАП 5: REFERENCES
    # ============================================================

    def _build_references(self):
        for imp, target in self._import_targets:
            canonical = self._canonical(target)
            if canonical is not None:
                self.all_references.append(
                    Reference(canonical, "import", imp.file, imp.line, imp.scope)
                )
        for cs in self.all_call_sites:
            if cs.resolution == "internal" and cs.target in self.symbols:
                self.all_references.append(Reference(cs.target, "call", cs.file, cs.line, cs.scope))

    # ============================================================
    # ПУБЛИЧНЫЕ МЕТОДЫ (для CLI)
    # ============================================================

    def resolve(self, name: str) -> str | None:
        """Canonical qualified name для запроса или None."""
        return self._canonical(name)

    def definitions(self, qualified_name: str) -> list[Symbol]:
        canonical = self.resolve(qualified_name)
        return list(self.defs.get(canonical, [])) if canonical else []

    def definition(self, qualified_name: str) -> list[Symbol]:
        return self.definitions(qualified_name)

    def references(self, qualified_name: str) -> list[Reference]:
        canonical = self.resolve(qualified_name)
        if canonical is None:
            return []
        refs = [r for r in self.all_references if r.target == canonical]
        return sorted(refs, key=lambda r: (r.file, r.line, r.kind))

    def callers(self, qualified_name: str) -> list[Symbol]:
        canonical = self.resolve(qualified_name)
        if canonical is None or not self.graph:
            return []
        return [self.symbols[qn] for qn in self.graph.callers(canonical) if qn in self.symbols]

    def call_sites(self, qualified_name: str) -> list[CallSite]:
        return [cs for cs in self.all_call_sites if cs.scope == qualified_name]

    def path(self, source: str, target: str) -> list[str] | None:
        if not self.graph:
            return None
        src = self.resolve(source)
        tgt = self.resolve(target)
        if src is None or tgt is None:
            return None
        return self.graph.shortest_path(src, tgt)

    def callees(self, qualified_name: str) -> dict:
        """Вызовы внутри символа.

        {"results": [Symbol, ...]  # internal, без повторов
         "external": [...], "unresolved": [...]}
        """
        canonical = self.resolve(qualified_name) or qualified_name

        results: list[Symbol] = []
        seen: set[str] = set()
        external = []
        unresolved = []

        for cs in self.call_sites(canonical):
            if cs.resolution == "internal" and cs.target:
                sym = self.symbols.get(cs.target)
                if sym is not None and cs.target not in seen:
                    seen.add(cs.target)
                    results.append(sym)
            elif cs.resolution == "external":
                external.append(
                    {
                        "expression": cs.expression,
                        "target": cs.target,
                        "file": cs.file,
                        "line": cs.line,
                    }
                )
            else:
                unresolved.append(
                    {
                        "expression": cs.expression,
                        "file": cs.file,
                        "line": cs.line,
                        "reason": cs.reason or "unknown",
                    }
                )

        return {"results": results, "external": external, "unresolved": unresolved}
