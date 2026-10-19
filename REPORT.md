# Отчет

## 1. Представление

Индекс строится в пять проходов по всем `.py` файлам: определения, imports, вызовы с разрешением
имен, граф, references. Все хранится в `RepoIndex` (`src/repo_map/index.py`).

**Qualified names.** `--root` указывает на каталог пакета, его имя становится пакетом верхнего
уровня. Имя символа — имя модуля плюс цепочка вложенных определений:
`fastapi.applications.FastAPI.setup.openapi` (функция, вложенная в метод `setup`).

**Что хранится:**

| сущность | поля | где |
|---|---|---|
| `Symbol` | `qualified_name`, `kind` (`module` / `class` / `method` / `function`), `file`, `line`, `async` | `symbols: qualified_name -> Symbol`; `defs` — список, если имя определено дважды (ветки `if` / `try`) |
| `Import` | `module` (как написано, в том числе `.b`), `name`, `alias`, `file`, `line`, `scope` | `all_imports` |
| привязки имен | локальное имя → (`module` или `symbol`, абсолютное имя цели) | `bindings[модуль]`, только imports верхнего уровня |
| `CallSite` | `expression`, `file`, `line`, `scope`, `resolution` (`internal` / `external` / `unresolved`), `target`, `reason` | `all_call_sites` |
| `Reference` | `target` (canonical имя), `kind` (`import` / `call`), `file`, `line`, `scope` | `all_references` |
| call graph | ребро `scope -> target` для каждого `internal`-вызова | `networkx.DiGraph` в `graph.py` |

**Scope** — ближайший охватывающий символ: функция или метод, иначе класс (код в теле класса),
иначе модуль. Декоратор вычисляется в охватывающей области, поэтому вызов в декораторе относится
к ней, а не к декорированной функции. Лямбды символов не создают, их вызовы относятся к
охватывающему символу. `line` у определения — строка с `def` или `class`, не строка декоратора.

На всем FastAPI (`95f8322`) индекс содержит 48 модулей и 550 символов (115 классов, 205 методов,
182 функции), 2658 call sites (625 `internal`, 1489 `external`, 544 `unresolved`) и 416 ребер.
Строится примерно за 0.6 с.

## 2. Разрешение имен

Дерево обходится с цепочкой лексических областей (модуль, класс, функция, лямбда). Для каждой
функции заранее собираются локальные имена: параметры, цели присваиваний, `for`, `with ... as`,
`except ... as`, локальные imports. Имя ищется от внутренней области к внешней, потом в модуле,
потом в imports. Найденное имя раскрывается функцией `_canonical`, которая проходит по imports и
re-export (цепочкой, с защитой от циклов) до места определения.

| правило | пример | результат |
|---|---|---|
| имя из того же модуля | `normalize(value)` в `b.py` | `tiny_pkg.b.normalize` |
| вложенная функция | `def outer(): def inner(): …; inner()` | `….outer.inner` |
| `from`-import, alias, relative | `from .b import helper as run_helper; run_helper()` | `tiny_pkg.b.helper` |
| import модуля и атрибут | `from . import b; b.helper()` | `tiny_pkg.b.helper` |
| то же через `import` | `import pkg.b as b; b.helper()`, `import pkg.b; pkg.b.helper()` | `pkg.b.helper` |
| re-export, в том числе цепочкой | `tiny_pkg.public_api` | `tiny_pkg.a.public_api` |
| вызов класса | `b.Formatter()` | `tiny_pkg.b.Formatter` (класс, не `__init__`) |
| `self.method()` | `self._wrap(x)` в `Formatter.format` | `tiny_pkg.b.Formatter._wrap` |
| перекрытие локальным именем | `def f(helper): helper()` | `unresolved` (не `mod.helper`) |

`self.method()` разрешается, только если `self` — первый параметр обычного метода (не
`staticmethod` / `classmethod`), не переприсвоен в теле, а `method` определен в теле того же
класса. Вызов за пределы пакета (`json.dumps`) и встроенные функции (`len` → `builtins.len`)
получают статус `external`, но никогда `internal`.

Принцип: если цель нельзя установить по этим правилам, вызов остается `unresolved` с причиной
(`unknown name`, `local variable`, `dynamic receiver`, `not defined in class`,
`self in nested function`), а не превращается в предположение. Так `obj.method()`, методы базовых
классов, `super()`, `cls.method()`, `getattr`, `importlib.import_module` и `import *` не дают
ложных ребер.

## 3. Ограничение

**`fastapi/routing.py:352`**, функция `fastapi.routing.run_endpoint_function`:

```python
async def run_endpoint_function(
    *, dependant: Dependant, values: dict[str, Any], is_coroutine: bool
) -> Any:
    ...
    if is_coroutine:
        return await dependant.call(**values)
```

Индекс помечает вызов `dependant.call` как `unresolved` (причина: `local variable (dynamic
receiver, no type inference)`), и в графе нет ребра от `run_endpoint_function` к обработчику
запроса. Так получилось по двум причинам:

1. `dependant` — параметр, а правило разрешения атрибутов работает только для модулей и `self`.
   Чтобы понять, что `dependant` это `Dependant`, нужен type inference по аннотации.
2. Даже с известным типом ответа нет. `call` в `Dependant` — не метод, а поле:
   `call: Callable[..., Any] | None = None` (`fastapi/dependencies/models.py`). Поле хранит
   функцию-обработчик, которую разработчик приложения передает при регистрации маршрута
   (`APIRoute(path, endpoint)` → `get_dependant(call=endpoint)`). Какая именно функция там
   окажется, определяется кодом пользователя фреймворка и значением на момент вызова.

Для правильного ответа понадобились бы type inference и межпроцедурный data-flow, а для
конкретного приложения еще и анализ его регистрации маршрутов. По одному коду FastAPI это принципиально
неизвестно, поэтому честное `unresolved` лучше любого `internal`-ребра: любое такое ребро было бы
ложным.

## 4. Использование AI

На LLM было делегировано написание кода и тестов для задания. При написании кода задания было замечено несоответствие некоторых полей, это было замечено при ошибочных запусках и по несоотвествию результатов заранее написанных тестов.
Также LLM применялось для отладки решения по результатам тестов для ошибок синтаксиса рабочих файлов (также несовпадение решения в index и test-файлах).
На LLM было делегировано оформление отчета в формат Markdown и составление таблиц, для которых был необходим анализ кода.
