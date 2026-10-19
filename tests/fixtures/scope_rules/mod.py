def helper():
    return 1


def make_decorator(name):
    return lambda f: f


@make_decorator("x")
def decorated():
    return helper()


class Holder:
    value = helper()

    @make_decorator("y")
    def method(self):
        return helper()
