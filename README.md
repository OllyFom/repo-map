# repo-map

Индекс Python-репозитория на Tree-sitter: определения, imports, вызовы и пять запросов
к приближенному call graph (`definition`, `references`, `callers`, `callees`, `path`).

Анализ идет только по исходному коду, анализируемый проект не импортируется и не исполняется.
Для разбора используется только Tree-sitter, для графа — NetworkX.

## Запуск

Нужен только [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv sync
uv run repo-map --help
```

Для работы с FastAPI клонируйте его **рядом** с проектом (analysis root — каталог пакета `fastapi/`):

```text
work/
├── repo-map/     этот проект
└── fastapi/      клон FastAPI
    └── fastapi/  ← это --root
```

```bash
cd work
git clone https://github.com/fastapi/fastapi.git
git -C fastapi checkout 95f8322     # release 0.141.1
```

## Запросы

Общий вид: `uv run repo-map <запрос> SYMBOL --root ROOT`. `SYMBOL` — qualified name символа
или имя, которое через imports и re-export ведет к символу (`fastapi.FastAPI`). В выводе всегда
canonical имя, то есть имя по месту определения.

### definition

```bash
uv run repo-map definition fastapi.FastAPI --root ../fastapi/fastapi
```

```json
{
  "query": "definition",
  "input": "fastapi.FastAPI",
  "symbol": "fastapi.applications.FastAPI",
  "results": [
    {
      "qualified_name": "fastapi.applications.FastAPI",
      "kind": "class",
      "file": "fastapi/applications.py",
      "line": 42,
      "async": false
    }
  ]
}
```

Имя из `fastapi/__init__.py` (`from .applications import FastAPI as FastAPI`) раскрыто через re-export.

### references

```bash
uv run repo-map references fastapi.openapi.utils.get_openapi_path --root ../fastapi/fastapi
```

```json
{
  "query": "references",
  "input": "fastapi.openapi.utils.get_openapi_path",
  "symbol": "fastapi.openapi.utils.get_openapi_path",
  "results": [
    {
      "kind": "call",
      "file": "fastapi/openapi/utils.py",
      "line": 394,
      "scope": "fastapi.openapi.utils.get_openapi_path"
    },
    {
      "kind": "call",
      "file": "fastapi/openapi/utils.py",
      "line": 631,
      "scope": "fastapi.openapi.utils.get_openapi"
    },
    {
      "kind": "call",
      "file": "fastapi/openapi/utils.py",
      "line": 651,
      "scope": "fastapi.openapi.utils.get_openapi"
    }
  ]
}
```

Виды ссылок: `import` и `call`.

### callers

```bash
uv run repo-map callers fastapi.openapi.utils.get_openapi --root ../fastapi/fastapi
```

```json
{
  "query": "callers",
  "input": "fastapi.openapi.utils.get_openapi",
  "symbol": "fastapi.openapi.utils.get_openapi",
  "results": [
    {"qualified_name": "fastapi.applications.FastAPI.openapi", "kind": "method",
     "file": "fastapi/applications.py", "line": 1070, "async": false}
  ]
}
```

### callees

```bash
uv run repo-map callees tiny_pkg.a.render --root tests/fixtures/tiny_pkg
```

```json
{
  "query": "callees",
  "input": "tiny_pkg.a.render",
  "symbol": "tiny_pkg.a.render",
  "results": [
    {
      "qualified_name": "tiny_pkg.b.Formatter",
      "kind": "class",
      "file": "tiny_pkg/b.py",
      "line": 9,
      "async": false
    }
  ],
  "external": [
    {
      "expression": "json.dumps",
      "target": "json.dumps",
      "file": "tiny_pkg/a.py",
      "line": 13
    }
  ],
  "unresolved": [
    {
      "expression": "formatter.format",
      "file": "tiny_pkg/a.py",
      "line": 13,
      "reason": "local variable (dynamic receiver, no type inference)"
    }
  ]
}
```

`results` — вызовы, разрешенные в символы проекта (без повторов), `external` — вызовы за пределы
пакета (включая `builtins.*`), `unresolved` — вызовы, цель которых нельзя установить по
поддержанным правилам.

### path

```bash
uv run repo-map path fastapi.applications.FastAPI.openapi fastapi.openapi.utils.get_openapi_path \
    --root ../fastapi/fastapi
```

```json
{
  "query": "path",
  "source": "fastapi.applications.FastAPI.openapi",
  "target": "fastapi.openapi.utils.get_openapi_path",
  "path": [
    "fastapi.applications.FastAPI.openapi",
    "fastapi.openapi.utils.get_openapi",
    "fastapi.openapi.utils.get_openapi_path"
  ]
}
```

Если пути нет, `"path": null`.

### Ошибки

| ситуация | stdout | stderr | код выхода |
|---|---|---|---|
| запрос выполнен, даже с пустым результатом | JSON | — | 0 |
| символ не найден | пусто | `repo-map: unknown symbol: …` | 1 |
| неверные аргументы, `--root` не каталог | пусто | usage | 2 |

## Формат JSON

Базовый формат из условия задания, поля сверх него не добавлялись. Единственное, что решает
реализация, — текст `reason` у unresolved-вызовов:

| `reason` | когда |
|---|---|
| `unknown name` | имя не найдено ни локально, ни в модуле, ни в imports (в том числе имя из `import *`) |
| `local variable` | вызов имени, связанного локально (параметр, присваивание, локальный import, лямбда) |
| `local variable (dynamic receiver, no type inference)` | `obj.method()`, где `obj` — локальное имя: тип неизвестен |
| `dynamic receiver` | получатель — не простое имя: `f().x()`, `getattr(o, "x")()`, `super().m()` |
| `not defined in class` | `self.m()`, но `m` не определен в теле того же класса (в том числе унаследован) |
| `self in nested function` | `self.m()` внутри функции, вложенной в метод |
| `not callable` | имя ведет к символу проекта, который нельзя вызвать (например, модуль) |

## Как устроено

Работа идет в пять проходов по всем `.py` файлам (`src/repo_map/index.py`):

1. **Определения.** Модули, классы, функции и методы (включая `async` и вложенные) складываются
   в `symbols: qualified_name -> Symbol`. Имя, определенное несколько раз (ветки `if`/`try`),
   хранится списком в `defs`.
2. **Imports.** Разбираются все шесть форм (`import m`, `import m as a`, `from m import s`,
   `from m import s as a`, `from .m import s`, `from ..m import s`). Для каждого модуля строится
   таблица `bindings: локальное имя -> цель`. Учитываются только imports верхнего уровня модуля
   (включая `if`/`try`).
3. **Вызовы.** Дерево обходится с цепочкой лексических областей (модуль, класс, функция, лямбда).
   У каждой функции заранее собираются локальные имена: параметры, цели присваиваний, `for`,
   `with ... as`, `except ... as`, локальные imports. Scope вызова — ближайший охватывающий символ;
   декоратор вычисляется в охватывающей области.
4. **Разрешение имен.** Вызов получает статус `internal`, `external` или `unresolved`.
   Имена раскрываются через `_canonical`: он проходит по imports и re-export (в том числе цепочкой,
   с защитой от циклов) до места определения.
5. **Граф и references.** Каждый `internal`-вызов дает ребро `scope -> target` в `networkx.DiGraph`
   (`src/repo_map/graph.py`). References строятся из imports и разрешенных вызовов.

Правило: **ложное уверенное ребро хуже честного `unresolved`**. Если цель нельзя установить
по поддержанным правилам, вызов остается `unresolved`.

## Поддержанные правила разрешения имен

| # | правило | пример |
|---|---|---|
| 1 | имя из того же модуля | `normalize(value)` → `tiny_pkg.b.normalize` |
| 2 | вложенная функция | `inner()` в `outer` → `….outer.inner` |
| 3 | `from`-import, alias, relative | `from .b import helper as run_helper; run_helper()` |
| 4 | import модуля и атрибут | `from . import b; b.helper()` |
| 5 | то же через `import` | `import pkg.b as b; b.helper()`, `import pkg.b; pkg.b.helper()` |
| 6 | re-export, в том числе цепочкой | `tiny_pkg.public_api` → `tiny_pkg.a.public_api` |
| 7 | вызов класса | `b.Formatter()` → сам класс, не `__init__` |
| 8 | `self.method()` | `self._wrap(x)` → `tiny_pkg.b.Formatter._wrap` |
| 9 | перекрытие локальным именем | `def f(helper): helper()` — **не** `mod.helper` |

## Что остается unresolved

- type inference и произвольный `obj.method()`;
- методы базовых классов, `super()`, `cls.method()`;
- `self` внутри функции, вложенной в метод;
- imports внутри функций;
- `getattr`, monkey patching, динамические imports (`importlib.import_module`, `__import__`),
  `import *`;
- семантика декораторов во время выполнения и dependency injection FastAPI.

Пример из FastAPI: `fastapi/routing.py:352`, `dependant.call(**values)` — `dependant` это
параметр, его тип неизвестен без type inference.

## Структура проекта

```text
src/repo_map/
    parser.py      настройка Tree-sitter, node_text(), line_of()
    model.py       Symbol, Import, CallSite, Reference
    index.py       RepoIndex: определения, imports, вызовы, разрешение имен, запросы
    graph.py       CallGraph на networkx (callers, callees, shortest_path)
    cli.py         CLI и формат JSON

scripts/
    print_tree.py  печать syntax tree файла

tests/
    fixtures/      маленькие пакеты с известным ground truth (по одному на тест)
    test_*.py      разрешенные тесты, см. ниже
    tests_unresolved неразрешенные тесты, см. ниже
```

## Тесты

Каждый тест строит `RepoIndex.build(<фикстура>)` и проверяет определения, `callees`, `callers`
и `references`. `--root` — каталог пакета, поэтому имя папки фикстуры становится именем пакета
верхнего уровня.

| файл | что проверяет | фикстура |
|---|---|---|
| `test_parser_smoke.py` | окружение: Tree-sitter, имена модулей, `--help` | `tiny_pkg` |
| `test_same_module.py` | правило 1: имя из того же модуля | `same_module` |
| `test_nested_func.py` | правило 2: вложенная функция | `nested_func` |
| `test_from_alias.py` | правило 3: `from`-import, alias, relative | `from_alias/rule3_from_alias` |
| `test_from_module.py` | правило 4: `from . import b; b.helper()` | `from_module/rule4_from_module` |
| `test_import_alias.py` | правило 5: `import pkg.b as b` и `import pkg.b` | `import_alias/pkg` |
| `test_reexport.py` | правило 6: re-export через `__init__.py` | `tiny_pkg` |
| `test_class_call.py` | правило 7: вызов класса | `class_call/rule7_class_call` |
| `test_self_method.py` | правило 8: `self.method()` | `tiny_pkg` |
| `test_shadow.py` | правило 9: перекрытие параметром, присваиванием, лямбдой | `shadow/rule9_shadow` |
| `test_scope_rules.py` | scope: декораторы, тело класса, строка `def` у декорированной функции | `scope_rules` |
| `test_unresolved/` | «честный unresolved», отсутствие ложных ребер: type inference, dynamic receiver, unknown name, наследование, `super()`, `cls`, `self` во вложенной функции, `getattr`, monkey patching, динамические imports, `import *` | `unresolved/*` |
| `test_fastapi_smoke.py` | публичные проверки на FastAPI (маркер `fastapi`) | клон FastAPI |

## Проверки

```bash
uv run pytest -q
uv run pytest -q -m fastapi   # публичные smoke tests, нужен ../fastapi
uv run ruff check .
uv run ruff format --check .
```

- `-m fastapi` запускает только 4 smoke-теста на FastAPI; остальные тесты при этом отсеиваются
  (`deselected`), это не пропуск. Если клон лежит не рядом, укажите его через
  `FASTAPI_ROOT=/path/to/fastapi/fastapi`.
- `tests/fixtures` исключены из `ruff` (`extend-exclude` в `pyproject.toml`): фикстуры нарочно
  содержат `import *`, присваивание лямбды и неопределенные имена, а переформатирование сдвинуло
  бы номера строк, которые проверяют тесты.