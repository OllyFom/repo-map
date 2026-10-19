import importlib

from .star_source import *


def helper():
    return 1


class Target:
    def method(self):
        return 1


def replacement():
    return 2


# имя атрибута в переменной: ruff не превращает getattr/setattr в обычный доступ
HELPER_NAME = "helper"
METHOD_NAME = "method"


def use_getattr(obj):
    return getattr(obj, HELPER_NAME)()


def use_setattr_patch():
    setattr(Target, METHOD_NAME, replacement)
    return Target().method()


def use_star_name():
    return star_func()


def use_import_module():
    return importlib.import_module("unresolved_dynamic.star_source").star_func()


def use_dunder_import():
    return __import__("unresolved_dynamic.star_source").star_func()
