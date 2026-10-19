# import * — все имена неизвестны
from some_module import *


def use_star():
    return unknown_from_star()  # unresolved: import *


# import внутри функции
def use_local_import():
    import json

    return json.dumps({"x": 1})  # unresolved: import внутри функции (или external)


def use_from_local_import():
    from os import path

    return path.exists("/tmp")  # unresolved: import внутри функции
