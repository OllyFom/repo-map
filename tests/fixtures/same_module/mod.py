def helper(value):
    return value + 1


def normalize(value):
    return value.strip().lower()


def use_helper(x):
    return helper(x)


def use_normalize(x):
    return normalize(x)


def use_both(x):
    h = helper(x)
    return normalize(h)
