class Base:
    def base_method(self):
        return 1


class Derived(Base):
    def derived_method(self):
        return self.base_method()  # unresolved: базовый класс (если не резолвим наследование)


class WithSuper:
    def method(self):
        return super().other_method()  # unresolved: super()


class WithCls:
    @classmethod
    def class_method(cls):
        return cls.another_method()  # unresolved: cls.method()
