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
from typing import Any, Optional


class Validator(ABC):

    def __set_name__(self, owner, name):
        self.private_name = "_" + name

    def __get__(self, obj, owner=None):
        return getattr(obj, self.private_name)

    def __set__(self, obj, value):
        self.validate(value)
        setattr(obj, self.private_name, value)

    @abstractmethod
    def validate(self, value: Any) -> None:
        pass


class NumValue(Validator):
    """Class to validate type and range of an input number."""

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
        """Initialize  the object.

        Args:
            type_spec: type of the number (int, float, int | float)
            gte: specifies boundary of greater than or equal for the
                 input value on the validate method
            gt: specifies boundary of greater than for the
                input value on the validate method
            lt: specifies boundary of less than for the
                 input value on the validate method
            lte: specifies boundary of greater than or equal for the
                input value on the validate method

        Raises:
            TypeError: 1) Invalid type specification: type_spec. Only int,
                          float, or int | float are allowed.
                       2) Expected gt to be of type x, got y.
                       3) Expected gte to be of type x, got y.
                       4) Expected lt to be of type x, got y.
                       5) Expected lte to be of type x, got y.
            ValueError: 1) Cannot set both 'gt' and 'gte' limits.
                        2) Cannot set both 'lt' and 'lte' limits.
                        3) Expected gt to be < lt.
                        4) Expected gt to be < lte.
                        5) Expected gte to be < lt.
                        6) Expected gte to be <= lte.

        """

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

        if gt is not None and not isinstance(gt, type_spec):
            raise TypeError(
                f"Expected {gt=} to be of type {type_spec}, got {type(gt).__name__}."
            )
        if gte is not None and not isinstance(gte, type_spec):
            raise TypeError(
                f"Expected {gte=} to be of type {type_spec}, got {type(gte).__name__}."
            )
        if lt is not None and not isinstance(lt, type_spec):
            raise TypeError(
                f"Expected {lt=} to be of type {type_spec}, got {type(lt).__name__}."
            )
        if lte is not None and not isinstance(lte, type_spec):
            raise TypeError(
                f"Expected {lte=} to be of type {type_spec}, got {type(lte).__name__}."
            )
        if ((gt is not None) or (gte is not None)) and (
            (lt is not None) or (lte is not None)
        ):
            if gt is not None:
                if lt is not None:
                    if lt <= gt:
                        raise ValueError(f"Expected {gt=} to be < {lt=}.")
                else:
                    if lte <= gt:
                        raise ValueError(f"Expected {gt=} to be < {lte=}.")

            else:  # gte is not None
                if lt is not None:
                    if lt <= gte:
                        raise ValueError(f"Expected {gte=} to be < {lt=}.")
                else:
                    if lte < gte:
                        raise ValueError(f"Expected {gte=} to be <= {lte=}.")

        self._gte = gte
        self._gt = gt
        self._lt = lt
        self._lte = lte

    def validate(self, value) -> None:
        """Verify the value is correct type and within bounds.

        Args:
            value: value to be validted

        Raises:
            TypeError: Expected value to be of type x, got y.
            ValueError: 1) Expected value to be >= gte.
                        2) Expected value to be > gt.
                        3) Expected value to be < lt.
                        4) Expected value to be <= lte.


        """
        # Strict type check: isinstance(True, int) is True, so we must exclude bool explicitly
        if not isinstance(value, self._type_spec) or type(value) is bool:
            raise TypeError(
                f"Expected {value=} to be of type {self._type_spec}, got {type(value).__name__}."
            )

        if self._gte is not None and not (value >= self._gte):
            raise ValueError(f"Expected {value=} to be >= {self._gte}.")

        if self._gt is not None and not (value > self._gt):
            raise ValueError(f"Expected {value=} to be > {self._gt}.")

        if self._lt is not None and not (value < self._lt):
            raise ValueError(f"Expected {value=} to be < {self._lt}.")

        if self._lte is not None and not (value <= self._lte):
            raise ValueError(f"Expected {value=} to be <= {self._lte}.")

    def _is_valid_spec(self, spec) -> bool:
        """Verify the typee spec is a valid number type.

        Args:
            spec: typee_spec to be validated

        Returns: True when spec is valid, False otherwise.

        """
        # Handle Union types (e.g., int | float)
        if isinstance(spec, types.UnionType):
            # Ensure every type inside the union is allowed (and reject bool)
            return all(t in self.ALLOWED_TYPES and t is not bool for t in spec.__args__)

        # Handle single types (ensure it's exactly int or float, and reject bool)
        return spec in self.ALLOWED_TYPES and spec is not bool


class ChoseOne(Validator):
    """Class to validate an input is among a set of valid choices."""

    def __init__(self, *, type_spec, choices: tuple) -> None:
        """Initialize  the object.

        Args:
            type_spec: type of the choices
            choices: values of type type_spec that are considered to
                     be valid for an input value for the validate method

        Raises:
            TypeError: Expected choice=choice to be of type x, got y

        """
        self._type_spec = type_spec
        self._choices = set(choices)

        # make sure type of choices agree with type_spec
        for choice in choices:
            if not isinstance(choice, type_spec):
                raise TypeError(
                    f"Expected {choice=} to be of type {type_spec}, got {type(choice).__name__}."
                )

    def validate(self, value: Any) -> None:
        """Verify the input to be among a set of choices.

        Args:
            value: value to be verified

        Raises:
            TypeError: Expected value=value to be of type x, got y
            ValueError: Expected value=value to be one of choices

        """
        if not isinstance(value, self._type_spec):
            raise TypeError(
                f"Expected {value=} to be of type {self._type_spec}, got {type(value).__name__}."
            )
        if value not in self._choices:
            raise ValueError(f"Expected {value=} to be one of {self._choices}.")


class TrueFalse(Validator):
    """Class to validate an input is boolean True or False."""

    def __init__(self):
        """Initialize the object."""
        self._type_spec = bool

    def validate(self, value: bool) -> None:
        """Verify the input is boolean True or False.

        Args:
            value: boolean True or False

        Raises:
            TypeError: Expected type(value) to be of type bool

        """
        if not isinstance(value, self._type_spec):
            raise TypeError(f"Expected {type(value)=} to be of type {self._type_spec}.")
