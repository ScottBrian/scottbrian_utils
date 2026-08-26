"""Module validator.

=========
Validator
=========

The Validator class is an abstract class used to create custom
validation classes to use when instantiation a class. Also included are
some basic validation routines that can be used:
1) Number: used to validate a number as being int or float and
   optionally having a minimum and/or maximum value.


:Example1: varify an input value is an int or float with a value greater
           or equal to 1

.. code-block:: python

    from scottbrian_utils.validator import NumValue

    class MyClass():
        val1 = NumValue(num_type=int, minvalue=1, maxvalue=5)

        def __init__(self, val1: int):
            self.val1 = val1

    my_class_a = MyClass(val1=1)  # OK
    my_class_b = MyClass(val1=0)  # ValueError
    my_class_c = MyClass(val1=6)  # ValueError
    my_class_d = MyClass(val1='1')  # TypeError
    my_class_e = MyClass(val1=1.2)  # TypeError


"""

from abc import ABC, abstractmethod


class Validator(ABC):

    def __set_name__(self, owner, name):
        self.private_name = "_" + name

    def __get__(self, obj, owner=None):
        return getattr(obj, self.private_name)

    def __set__(self, obj, value):
        self.validate(value)
        setattr(obj, self.private_name, value)

    @abstractmethod
    def validate(self, value):
        pass


class NumValue(Validator):

    def __init__(self, *, type: type, minvalue=None, maxvalue=None):
        self.type = type
        self.minvalue = minvalue
        self.maxvalue = maxvalue

    def validate(self, value):
        if not isinstance(value, self.type):
            raise TypeError(f"Expected {value=} to be of type {self.type}")
        if self.minvalue is not None and value < self.minvalue:
            raise ValueError(f"Expected {value=} to be no less than {self.minvalue}")
        if self.maxvalue is not None and self.maxvalue < value:
            raise ValueError(f"Expected {value=} to be no greater than {self.maxvalue}")


class ChoseOne(Validator):

    def __init__(self, *, type: type, choices: tuple):
        self.type = type
        self.choices = set(choices)

    def validate(self, value):
        if not isinstance(value, self.type):
            raise TypeError(f"Expected {value=} to be of type {self.type}")
        if value not in self.choices:
            raise ValueError(f"Expected {value=} to be one of {self.choices}")


class True_False(Validator):

    def __init__(self):
        self.type = bool

    def validate(self, value):
        if not isinstance(value, bool):
            raise TypeError(f"Expected {type(value)=} to be of type {self.type}")
