class MyClass:
    def inner_method(self):
        return 1

    def outer_method(self):
        def inner_function():
            return self.inner_method()

        return inner_function()
