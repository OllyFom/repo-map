from . import b


def use_module_function(x):
    return b.helper(x)


def use_module_class(x):
    fmt = b.Formatter()
    return fmt.format(x)


def use_both(x):
    h = b.helper(x)
    fmt = b.Formatter()
    return fmt.format(h)
