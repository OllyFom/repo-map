from .b import helper as run_helper
from .b import normalize


def use_alias(x):
    return run_helper(x)


def use_direct(x):
    return normalize(x)


def use_both(x):
    h = run_helper(x)
    return normalize(h)
