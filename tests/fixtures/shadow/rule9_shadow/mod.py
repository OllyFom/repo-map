def helper(value):
    return value + 1


def normalize(value):
    return value.strip().lower()


# Правило 9: параметр перекрывает имя функции
def shadow_by_parameter(helper):
    return helper(1)  # helper — это параметр, не функция из модуля


# Правило 9: локальная переменная перекрывает имя функции
def shadow_by_assignment():
    normalize = "not a function"
    return normalize("test")  # normalize — это переменная, не функция


# Правило 9: локальная переменная перекрывает имя из импорта
def shadow_imported():
    helper = lambda x: x * 2
    return helper(5)  # helper — это лямбда, не функция из модуля


# Обычный вызов (не перекрыт) — для сравнения
def normal_call():
    return helper(10)  # это настоящий helper из модуля
