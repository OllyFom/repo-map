from . import b


def create_formatter():
    return b.Formatter()


def create_processor(name):
    return b.Processor(name)


def use_classes():
    fmt = b.Formatter()
    proc = b.Processor("test")
    return fmt, proc
