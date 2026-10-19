class Base:
    def base_method(self):
        return 1


class Derived(Base):
    def derived_method(self):
        return self.base_method()


class WithSuper(Base):
    def method(self):
        return super().base_method()


class WithCls:
    @classmethod
    def helper(cls):
        return 1

    @classmethod
    def class_method(cls):
        return cls.helper()
