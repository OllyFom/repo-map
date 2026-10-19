# Случай 1: type inference — obj.method() где obj — переменная
def use_object(obj):
    return obj.method()  # unresolved: type inference


# Случай 2: dynamic receiver — dependant.call(**values)
class Dependant:
    def call(self, **kwargs):
        pass


def execute(dependant):
    return dependant.call(**{"x": 1})  # unresolved: dynamic receiver


# Случай 3: local variable — переменная перекрывает имя
def helper():
    return 1


def use_local():
    helper = "not a function"
    return helper()  # unresolved: local variable


# Случай 4: unknown name — вызов несуществующего имени
def use_unknown():
    return unknown_function()  # unresolved: unknown name


# Случай 5: chained method — цепочка методов на переменной
def use_chained(obj):
    return obj.foo().bar()  # unresolved: type inference (оба вызова)
