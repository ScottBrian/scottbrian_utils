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
        val1 = NumValue(num_type=int, gte=1, lte=5)

        def __init__(self, val1: int):
            self.val1 = val1

    my_class_a = MyClass(val1=1)  # OK
    my_class_b = MyClass(val1=0)  # ValueError
    my_class_c = MyClass(val1=6)  # ValueError
    my_class_d = MyClass(val1='1')  # TypeError
    my_class_e = MyClass(val1=1.2)  # TypeError


:Example1: varify an input value is an int or float with a value greater
           or equal to 1

.. code-block:: python
    from scottbrian_utils.validator import ChoseOne

    class MyClass:
        val1 = ChoseOne(type=str, choices=("Good", "Bad", "Ugly"))

        def __init__(self, val1: str):
            self.val1 = val1

    my_class_a = MyClass(val1="Good")  # OK

    my_class_b = MyClass(val1="Best")  # ValueError

    my_class_c = MyClass(val1=1)  # TypeError


.. code-block:: python
    from scottbrian_utils.validator import True_False

    class MyClass:
        val1 = True_False()

        def __init__(self, val1: bool):
            self.val1 = val1

    my_class_a1 = MyClass(val1=True)  # OK
    my_class_a2 = MyClass(val1=False)  # OK

    my_class_b = MyClass(val1="True")  # TypeError
    my_class_b = MyClass(val1=1)  # TypeError


"""

import types
from abc import ABC, abstractmethod
from typing import Optional


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

    # Set of strictly allowed single types
    ALLOWED_TYPES = {int, float}

    def __init__(
        self,
        *,
        type_spec,
        gte: Optional[int | float] = None,
        gt: Optional[int | float] = None,
        lt: Optional[int | float] = None,
        lte: Optional[int | float] = None,
    ) -> None:
        if not self._is_valid_spec(type_spec):
            raise TypeError(
                f"Invalid type specification: {type_spec}. Only int, float, or int | float are allowed."
            )
        self._type_spec = type_spec

        # Prevent contradictory bounds
        if gt is not None and gte is not None:
            raise ValueError("Cannot set both 'gt' and 'gte' limits.")
        if lt is not None and lte is not None:
            raise ValueError("Cannot set both 'lt' and 'lte' limits.")

        self._gte = gte
        self._gt = gt
        self._lt = lt
        self._lte = lte

    def validate(self, value):
        # Strict type check: isinstance(True, int) is True, so we must exclude bool explicitly
        if not isinstance(value, self._type_spec) or type(value) is bool:
            raise TypeError(
                f"Expected {value=} to be of type {self._type_spec}, got {type(value).__name__}"
            )

        if self._gte is not None and not (value >= self._gte):
            raise ValueError(f"Expected {value=} to be >= {self._gte}")

        if self._gt is not None and not (value > self._gt):
            raise ValueError(f"Expected {value=} to be > {self._gt}")

        if self._lt is not None and not (value < self._lt):
            raise ValueError(f"Expected {value=} to be < {self._lt}")

        if self._lte is not None and not (value <= self._lte):
            raise ValueError(f"Expected {value=} to be <= {self._lte}")

    def _is_valid_spec(self, spec):
        # Handle Union types (e.g., int | float)
        if isinstance(spec, types.UnionType):
            # Ensure every type inside the union is allowed (and reject bool)
            return all(t in self.ALLOWED_TYPES and t is not bool for t in spec.__args__)

        # Handle single types (ensure it's exactly int or float, and reject bool)
        return spec in self.ALLOWED_TYPES and spec is not bool


class ChoseOne(Validator):

    def __init__(self, *, type_spec, choices: tuple):
        self._type_spec = type_spec
        self._choices = set(choices)

    def validate(self, value):
        if not isinstance(value, self._type_spec):
            raise TypeError(f"Expected {value=} to be of type {self._type_spec}")
        if value not in self._choices:
            raise ValueError(f"Expected {value=} to be one of {self._choices}")


class True_False(Validator):

    def __init__(self):
        self._type_spec = bool

    def validate(self, value):
        if not isinstance(value, self._type_spec):
            raise TypeError(f"Expected {type(value)=} to be of type {self._type_spec}")
