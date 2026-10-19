class Formatter:
    def format(self, value):
        return f"[{value}]"

    def _wrap(self, value):
        return f"<{value}>"


class Processor:
    def __init__(self, name):
        self.name = name

    def process(self, value):
        return value.upper()
