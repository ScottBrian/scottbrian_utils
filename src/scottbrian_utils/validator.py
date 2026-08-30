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
    from scottbrian_utils.validator import ChooseOne

    class MyClass:
        val1 = ChooseOne(type=str, choices=("Good", "Bad", "Ugly"))

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
from typing import Any, Generic, overload, Type, TypeVar

from numpy.f2py.crackfortran import optionalpattern

# T represents the type of value the descriptor manages (e.g., int, str)
T = TypeVar("T")
# InstanceT represents the class instance using the descriptor
InstanceT = TypeVar("InstanceT")
# OwnerT represents the class blueprint itself
OwnerT = TypeVar("OwnerT", bound=Type[Any])


class Validator(ABC, Generic[T]):
    """Abstract Base Class for all descriptors utilizing validation logic."""

    def __init__(self) -> None:
        self.private_name: str = ""

    def __set_name__(self, owner: Type[Any], name: str) -> None:
        self.private_name = f"_{name}"

    @overload
    def __get__(self, instance: None, owner: Type[Any]) -> "Validator[T]": ...

    @overload
    def __get__(self, instance: object, owner: Type[Any]) -> T: ...

    def __get__(self, instance: Any, owner: Type[Any]) -> Any:
        if instance is None:
            return self
        return getattr(instance, self.private_name)

    def __set__(self, instance: object, value: T) -> None:
        # Runs the custom validation subclass implementation before saving
        self.validate(value)
        setattr(instance, self.private_name, value)

    @abstractmethod
    def validate(self, value: Any) -> None:
        """Subclasses must implement this method to enforce type or bounds checks.

        Should raise TypeError or ValueError if the value is invalid.
        """
        raise NotImplementedError("Subclasses must implement validate()")

    async def async_validate(self, value: Any) -> None:
        """Optional async validation logic (e.g., DB lookup). Default is a no-op."""
        raise NotImplementedError("Subclasses must implement async_validate()")


# class NumValue(Validator):
#     """Class to validate type and range of an input number."""
#
#     # Set of strictly allowed single types
#     ALLOWED_TYPES = {int, float}
#
#     def __init__(
#         self,
#         *,
#         type_spec: int | float,
#         gte: Optional[int | float] = None,
#         gt: Optional[int | float] = None,
#         lt: Optional[int | float] = None,
#         lte: Optional[int | float] = None,
#     ) -> None:
#         """Initialize  the object.
#
#         Args:
#             type_spec: type of the number (int, float, int | float)
#             gte: specifies boundary of greater than or equal for the
#                  input value on the validate method
#             gt: specifies boundary of greater than for the
#                 input value on the validate method
#             lt: specifies boundary of less than for the
#                  input value on the validate method
#             lte: specifies boundary of greater than or equal for the
#                 input value on the validate method
#
#         Raises:
#             TypeError: 1) Invalid type specification: type_spec. Only int,
#                           float, or int | float are allowed.
#                        2) Expected gt to be of type x, got y.
#                        3) Expected gte to be of type x, got y.
#                        4) Expected lt to be of type x, got y.
#                        5) Expected lte to be of type x, got y.
#             ValueError: 1) Cannot set both 'gt' and 'gte' limits.
#                         2) Cannot set both 'lt' and 'lte' limits.
#                         3) Expected gt to be < lt.
#                         4) Expected gt to be < lte.
#                         5) Expected gte to be < lt.
#                         6) Expected gte to be <= lte.
#
#         """
#
#         if not self._is_valid_spec(type_spec):
#             raise TypeError(
#                 f"Invalid type specification: {type_spec}. Only int, float, or int | float are allowed."
#             )
#         self._type_spec = type_spec
#
#         # Prevent contradictory bounds
#         if gt is not None and gte is not None:
#             raise ValueError("Cannot set both 'gt' and 'gte' limits.")
#         if lt is not None and lte is not None:
#             raise ValueError("Cannot set both 'lt' and 'lte' limits.")
#
#         if gt is not None and not isinstance(gt, type_spec):
#             raise TypeError(
#                 f"Expected {gt=} to be of type {type_spec}, got {type(gt).__name__}."
#             )
#         if gte is not None and not isinstance(gte, type_spec):
#             raise TypeError(
#                 f"Expected {gte=} to be of type {type_spec}, got {type(gte).__name__}."
#             )
#         if lt is not None and not isinstance(lt, type_spec):
#             raise TypeError(
#                 f"Expected {lt=} to be of type {type_spec}, got {type(lt).__name__}."
#             )
#         if lte is not None and not isinstance(lte, type_spec):
#             raise TypeError(
#                 f"Expected {lte=} to be of type {type_spec}, got {type(lte).__name__}."
#             )
#         if ((gt is not None) or (gte is not None)) and (
#             (lt is not None) or (lte is not None)
#         ):
#             if gt is not None:
#                 if lt is not None:
#                     if lt <= gt:
#                         raise ValueError(f"Expected {gt=} to be < {lt=}.")
#                 else:
#                     if lte <= gt:
#                         raise ValueError(f"Expected {gt=} to be < {lte=}.")
#
#             else:  # gte is not None
#                 if lt is not None:
#                     if lt <= gte:  # typedef: ignore
#                         raise ValueError(f"Expected {gte=} to be < {lt=}.")
#                 else:
#                     if lte < gte:  # typedef: ignore
#                         raise ValueError(f"Expected {gte=} to be <= {lte=}.")
#
#         self._gte = gte
#         self._gt = gt
#         self._lt = lt
#         self._lte = lte
#
#     def validate(self, value: int | float) -> None:
#         """Verify the value is correct type and within bounds.
#
#         Args:
#             value: value to be validated
#
#         Raises:
#             TypeError: Expected value to be of type x, got y.
#             ValueError: 1) Expected value to be >= gte.
#                         2) Expected value to be > gt.
#                         3) Expected value to be < lt.
#                         4) Expected value to be <= lte.
#
#
#         """
#         # Strict type check: isinstance(True, int) is True, so we must exclude bool explicitly
#         if not isinstance(value, self._type_spec) or type(value) is bool:
#             raise TypeError(
#                 f"Expected {value=} to be of type {self._type_spec}, got {type(value).__name__}."
#             )
#
#         if self._gte is not None and not (value >= self._gte):
#             raise ValueError(f"Expected {value=} to be >= {self._gte}.")
#
#         if self._gt is not None and not (value > self._gt):
#             raise ValueError(f"Expected {value=} to be > {self._gt}.")
#
#         if self._lt is not None and not (value < self._lt):
#             raise ValueError(f"Expected {value=} to be < {self._lt}.")
#
#         if self._lte is not None and not (value <= self._lte):
#             raise ValueError(f"Expected {value=} to be <= {self._lte}.")
#
#     def _is_valid_spec(self, spec: int | float) -> bool:
#         """Verify the typee spec is a valid number type.
#
#         Args:
#             spec: typee_spec to be validated
#
#         Returns: True when spec is valid, False otherwise.
#
#         """
#         # Handle Union types (e.g., int | float)
#         if isinstance(spec, types.UnionType):
#             # Ensure every type inside the union is allowed (and reject bool)
#             return all(t in self.ALLOWED_TYPES and t is not bool for t in spec.__args__)
#
#         # Handle single types (ensure it's exactly int or float, and reject bool)
#         return spec in self.ALLOWED_TYPES and spec is not bool

# Reuse the numeric TypeVar from earlier
NumT = TypeVar("NumT", int, float)


class NumValue(Validator[NumT]):
    """Class to validate type and range of an input number."""

    ALLOWED_TYPES: set[type] = {int, float}

    @overload
    def __init__(
        self: "NumValue[int]",
        *,
        type_spec: Type[int],
        gte: int | None = None,
        gt: int | None = None,
        lt: int | None = None,
        lte: int | None = None,
    ) -> None: ...

    @overload
    def __init__(
        self: "NumValue[float]",
        *,
        type_spec: Type[float],
        gte: float | None = None,
        gt: float | None = None,
        lt: float | None = None,
        lte: float | None = None,
    ) -> None: ...

    @overload
    def __init__(
        self: "NumValue[int | float]",
        *,
        type_spec: types.UnionType,
        gte: int | float | None = None,
        gt: int | float | None = None,
        lt: int | float | None = None,
        lte: int | float | None = None,
    ) -> None: ...

    def __init__(
        self,
        *,
        type_spec: Type[Any] | types.UnionType,
        gte: int | float | None = None,
        gt: int | float | None = None,
        lt: int | float | None = None,
        lte: int | float | None = None,
    ) -> None:
        super().__init__()
        if not self._is_valid_spec(type_spec):
            # raise TypeError(f"Invalid type specification: {type_spec}.")
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
                    if lt <= gte:  # typedef: ignore
                        raise ValueError(f"Expected {gte=} to be < {lt=}.")
                else:
                    if lte < gte:  # typedef: ignore
                        raise ValueError(f"Expected {gte=} to be <= {lte=}.")
        self._gte, self._gt, self._lt, self._lte = gte, gt, lt, lte

    def validate(self, value: Any) -> None:
        if type(value) is bool:
            # raise TypeError(f"Expected number, got bool.")
            raise TypeError(
                f"Expected {value=} to be of type {self._type_spec}, got {type(value).__name__}."
            )
        if isinstance(self._type_spec, types.UnionType):
            if type(value) not in self._type_spec.__args__:
                raise TypeError(
                    f"Expected {value=} to be of type {self._type_spec}, got {type(value).__name__}."
                )
                # raise TypeError(
                #     f"Expected {self._type_spec}, got {type(value).__name__}"
                # )
        elif type(value) is not self._type_spec:
            raise TypeError(
                f"Expected {value=} to be of type {self._type_spec}, got {type(value).__name__}."
            )
            # raise TypeError(
            #     f"Expected {self._type_spec.__name__}, got {type(value).__name__}"
            # )

        # if self._gte is not None and value < self._gte:
        #     raise ValueError(f"Must be >= {self._gte}")
        # if self._gt is not None and value <= self._gt:
        #     raise ValueError(f"Must be > {self._gt}")
        # if self._lt is not None and value >= self._lt:
        #     raise ValueError(f"Must be < {self._lt}")
        # if self._lte is not None and value > self._lte:
        #     raise ValueError(f"Must be <= {self._lte}")

        if self._gte is not None and not (value >= self._gte):
            raise ValueError(f"Expected {value=} to be >= {self._gte}.")

        if self._gt is not None and not (value > self._gt):
            raise ValueError(f"Expected {value=} to be > {self._gt}.")

        if self._lt is not None and not (value < self._lt):
            raise ValueError(f"Expected {value=} to be < {self._lt}.")

        if self._lte is not None and not (value <= self._lte):
            raise ValueError(f"Expected {value=} to be <= {self._lte}.")

    def _is_valid_spec(self, spec: Any) -> bool:
        if isinstance(spec, types.UnionType):
            return all(t in self.ALLOWED_TYPES and t is not bool for t in spec.__args__)
        return spec in self.ALLOWED_TYPES and spec is not bool

### @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
# hybrid type_spec as optional
@overload
    def __init__(
        self: "NumValue[int]",
        *,
        type_spec: Optional[Type[int]] = None,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
    ) -> None: ...

    @overload
    def __init__(
        self: "NumValue[float]",
        *,
        type_spec: Optional[Type[float]] = None,
        gt: Optional[float] = None,
        gte: Optional[float] = None,
        lt: Optional[float] = None,
        lte: Optional[float] = None,
    ) -> None: ...

    def __init__(
        self,
        *,
        type_spec: Optional[Type[Any]] = None,
        gt: Optional[int | float] = None,
        gte: Optional[int | float] = None,
        lt: Optional[int | float] = None,
        lte: Optional[int | float] = None,
    ) -> None:
        super().__init__()

        # 1. Mutually exclusive boundary checks
        if gt is not None and gte is not None:
            raise ValueError("Cannot set both 'gt' and 'gte' limits.")
        if lt is not None and lte is not None:
            raise ValueError("Cannot set both 'lt' and 'lte' limits.")

        bounds = [v for v in (gt, gte, lt, lte) if v is not None]

        # 2. Hybrid Type Inference Resolution
        if type_spec is not None:
            if type_spec not in (int, float):
                raise TypeError("type_spec must be exactly 'int' or 'float'.")
            self._is_float_target = (type_spec is float)
        else:
            # No type_spec provided, try to infer from bounds
            if not bounds:
                raise ValueError(
                    "NumValue requires either a 'type_spec' or at least one boundary limit."
                )
            self._is_float_target = any(isinstance(b, float) for b in bounds)

        # 3. Validation of boundary types against the determined target type
        for b in bounds:
            if type(b) is bool:
                raise TypeError("Booleans are not allowed as boundary limits.")
            if self._is_float_target and type(b) is int:
                raise TypeError("All boundary arguments must be floats if target is float.")
            if not self._is_float_target and type(b) is float:
                raise TypeError("Cannot use float boundaries for an integer validator.")

        # ... (Rest of cross-boundary comparison and assignment remains identical) ...
## @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

from collections.abc import Collection

ChoiceT = TypeVar("ChoiceT")


class ChooseOne(Validator[ChoiceT]):
    """Class to validate that an input value belongs to a specific set of options."""

    def __init__(self, choices: Collection[ChoiceT]) -> None:
        super().__init__()
        if not choices:
            raise ValueError("Choices collection cannot be empty.")
        self._choices = set(choices)

    def validate(self, value: Any) -> None:
        # Strict checking: prevent True matching 1 or False matching 0 in collections
        if type(value) is bool and any(type(c) is not bool for c in self._choices):
            # If a bool is passed but choices are numbers, fail immediately
            if int(value) in self._choices:
                raise ValueError(f"Expected {value=} to be one of {self._choices}.")
                # raise ValueError(f"Value {value} is not an allowed choice.")

        if value not in self._choices:
            raise ValueError(f"Expected {value=} to be one of {self._choices}.")
            # raise ValueError(
            #     f"Value {value} is not an allowed choice. Options: {self._choices}"
            # )


class TrueFalse(Validator[bool]):
    """Class to ensure only actual True or False boolean values are allowed."""

    def validate(self, value: Any) -> None:
        if type(value) is not bool:
            raise TypeError(
                f"Expected {value=} to be of type bool," f" got {type(value).__name__}."
            )
            # raise TypeError(f"Expected a boolean, got type '{type(value).__name__}'.")


# class ChooseOne(Validator):
#     """Class to validate an input is among a set of valid choices."""
#
#     def __init__(self, *, type_spec, choices: tuple[Any]) -> None:
#         """Initialize  the object.
#
#         Args:
#             type_spec: type of the choices
#             choices: values of type type_spec that are considered to
#                      be valid for an input value for the validate method
#
#         Raises:
#             TypeError: Expected choice=choice to be of type x, got y
#
#         """
#         self._type_spec = type_spec
#         self._choices = set(choices)
#
#         # make sure type of choices agree with type_spec
#         for choice in choices:
#             if not isinstance(choice, type_spec):
#                 raise TypeError(
#                     f"Expected {choice=} to be of type {type_spec}, got {type(choice).__name__}."
#                 )
#
#     def validate(self, value: Any) -> None:
#         """Verify the input to be among a set of choices.
#
#         Args:
#             value: value to be verified
#
#         Raises:
#             TypeError: Expected value=value to be of type x, got y
#             ValueError: Expected value=value to be one of choices
#
#         """
#         if not isinstance(value, self._type_spec):
#             raise TypeError(
#                 f"Expected {value=} to be of type {self._type_spec}, got {type(value).__name__}."
#             )
#         if value not in self._choices:
#             raise ValueError(f"Expected {value=} to be one of {self._choices}.")
#
#
# class TrueFalse(Validator):
#     """Class to validate an input is boolean True or False."""
#
#     def __init__(self) -> None:
#         """Initialize the object."""
#         self._type_spec = bool
#
#     def validate(self, value: bool) -> None:
#         """Verify the input is boolean True or False.
#
#         Args:
#             value: boolean True or False
#
#         Raises:
#             TypeError: Expected type(value) to be of type bool
#
#         """
#         if not isinstance(value, self._type_spec):
#             raise TypeError(
#                 f"Expected {value=} to be of type {self._type_spec},"
#                 f" got {type(value).__name__}."
#             )
