"""test_validator.py module."""

########################################################################
# Standard Library
########################################################################
import logging
import os
import re
from typing import Any, TypeAlias, Union

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.testlib_verifier import verify_lib
from scottbrian_utils.validator import NumValue, ChoseOne

########################################################################
# logger
########################################################################
logger = logging.getLogger(__name__)

########################################################################
# type aliases
########################################################################
IntFloat: TypeAlias = Union[int, float]


########################################################################
# UniqueTS test exceptions
########################################################################
class ErrorValidator(Exception):
    """Base class for exception in this module."""

    pass


########################################################################
# TestValidatorCorrectSource
########################################################################
class TestValidatorCorrectSource:
    """Verify that we are testing with correctly built code."""

    ####################################################################
    # test_validator_correct_source
    ####################################################################
    def test_validator_correct_source(self) -> None:
        """Test validator correct source."""
        if "TOX_ENV_NAME" in os.environ:
            verify_lib(obj_to_check=NumValue)


########################################################################
# TestValidator
########################################################################
class TestValidatorNumValue:
    """Test validator NumValue."""

    ####################################################################
    # test_validator_numvalue_type_only
    ####################################################################
    def test_validator_numvalue_type_only(self) -> None:
        """Test validator NumValue type only.

        Test NumValue with only the type argument.

        """

        ################################################################
        # type=int
        ################################################################
        class MyClass:
            val1 = NumValue(type_spec=int)

            def __init__(self, val1: int):
                self.val1 = val1

        MyClass(val1=-999)  # OK
        MyClass(val1=-1)  # OK
        MyClass(val1=0)  # OK
        MyClass(val1=1)  # OK
        MyClass(val1=999)  # OK

        expected_error_msg = re.escape(
            "Expected value='1' to be of type <class 'int'>, got str."
        )
        with pytest.raises(TypeError, match=expected_error_msg):
            MyClass(val1="1")  # typedef: ignore

        expected_error_msg = re.escape(
            "Expected value=1.2 to be of type <class 'int'>, got float."
        )
        with pytest.raises(TypeError, match=expected_error_msg):
            MyClass(val1=1.2)  # typedef: ignore

        ################################################################
        # type=float
        ################################################################
        class MyClass:
            val1 = NumValue(type_spec=float)

            def __init__(self, val1: float):
                self.val1 = val1

        MyClass(val1=-999.9)  # OK
        MyClass(val1=-1.1)  # OK
        MyClass(val1=-0.1)  # OK
        MyClass(val1=0.0)  # OK
        MyClass(val1=0.1)  # OK
        MyClass(val1=1.1)  # OK
        MyClass(val1=999.9)  # OK

        expected_error_msg = re.escape(
            "Expected value=-999 to be of type <class 'float'>, got int."
        )
        with pytest.raises(TypeError, match=expected_error_msg):
            MyClass(val1=-999)  # typedef: ignore

        expected_error_msg = re.escape(
            "Expected value='1' to be of type <class 'float'>, got str."
        )
        with pytest.raises(TypeError, match=expected_error_msg):
            MyClass(val1="1")  # typedef: ignore

        ################################################################
        # type=float
        ################################################################

        class MyClass:
            val1 = NumValue(type_spec=int | float)

            def __init__(self, val1: float):
                self.val1 = val1

        MyClass(val1=-999)  # OK
        MyClass(val1=-999.9)  # OK
        MyClass(val1=-1.1)  # OK
        MyClass(val1=-1)  # OK
        MyClass(val1=-0.1)  # OK
        MyClass(val1=0)  # OK
        MyClass(val1=0.0)  # OK
        MyClass(val1=0.1)  # OK
        MyClass(val1=1)  # OK
        MyClass(val1=1.1)  # OK
        MyClass(val1=999)  # OK
        MyClass(val1=999.9)  # OK

        expected_error_msg = re.escape(
            "Expected value='1' to be of type int | float, got str."
        )
        with pytest.raises(TypeError, match=expected_error_msg):
            MyClass(val1="1")  # typedef: ignore

        ################################################################
        # type=str
        ################################################################
        expected_error_msg = re.escape(
            f"Invalid type specification: <class 'str'>. Only int, float, or int | float are allowed."
        )
        with pytest.raises(TypeError, match=expected_error_msg):

            class MyClass:
                val1 = NumValue(type_spec=str)

                def __init__(self, val1: float):
                    self.val1 = val1

        ################################################################
        # type=bool
        ################################################################
        expected_error_msg = re.escape(
            f"Invalid type specification: <class 'bool'>. Only int, float, or int | float are allowed."
        )
        with pytest.raises(TypeError, match=expected_error_msg):

            class MyClass:
                val1 = NumValue(type_spec=bool)

                def __init__(self, val1: float):
                    self.val1 = val1

    ####################################################################
    # test_validator_both_gt_gte_lt_lte
    ####################################################################
    def test_validator_both_gt_gte_lt_lte(self) -> None:
        """Test validator both gt and gte or both lt and lte.

        Test NumValue with int values.

        """

        ################################################################
        # both gt and gte
        ################################################################
        expected_error_msg = re.escape(f"Cannot set both 'gt' and 'gte' limits.")
        with pytest.raises(ValueError, match=expected_error_msg):

            class MyClass1:
                val1 = NumValue(type_spec=int, gte=3, gt=5, lt=1)

                def __init__(self, val1: int):
                    self.val1 = val1

        ################################################################
        # both gt and gte
        ################################################################
        expected_error_msg = re.escape(f"Cannot set both 'lt' and 'lte' limits.")
        with pytest.raises(ValueError, match=expected_error_msg):

            class MyClass2:
                val1 = NumValue(type_spec=int, lte=3, lt=5, gt=9)

                def __init__(self, val1: int):
                    self.val1 = val1

    ####################################################################
    # test_validator_numvalue_int_gte
    ####################################################################
    @pytest.mark.parametrize("gte_arg", (-3, -2, -1, 0, 1, 2, 3))
    def test_validator_numvalue_int_gte(self, gte_arg: int) -> None:
        """Test validator NumValue int gte.

        Test NumValue with int values.

        """

        ################################################################
        # type=int
        ################################################################
        class MyClass:
            val1 = NumValue(type_spec=int, gte=gte_arg)

            def __init__(self, val1: int):
                self.val1 = val1

        for val in range(-4, 5):
            if val < gte_arg:
                expected_error_msg = re.escape(
                    f"Expected value={val} to be >= {gte_arg}"
                )
                with pytest.raises(ValueError, match=expected_error_msg):
                    MyClass(val1=val)
            else:
                MyClass(val1=val)

    ####################################################################
    # test_validator_numvalue_int_gt
    ####################################################################
    restriction_vals = (
        None,
        -2.0,
        -2,
        -1.5,
        -1.0,
        -1,
        -0.5,
        0,
        0.0,
        0.5,
        1.0,
        1,
        1.5,
        2.0,
        2,
    )

    @pytest.mark.parametrize("type_spec_arg", (int, float, int | float, IntFloat))
    @pytest.mark.parametrize("gt_gte_arg", ("gt", "gte"))
    @pytest.mark.parametrize("lt_lte_arg", ("lt", "lte"))
    @pytest.mark.parametrize("min_arg", restriction_vals)
    @pytest.mark.parametrize("max_arg", restriction_vals)
    def test_validator_numvalue_int_gt(
        self,
        type_spec_arg: type[int] | type[float] | type[int | float] | type[IntFloat],
        gt_gte_arg: str,
        lt_lte_arg: str,
        min_arg: int | float,
        max_arg: int | float,
    ) -> None:
        """Test validator NumValue int gt.

        Test NumValue with int values.

        """
        if gt_gte_arg == "gt":
            gt_spec = min_arg
            gte_spec = None
        else:
            gt_spec = None
            gte_spec = min_arg
        if lt_lte_arg == "lt":
            lt_spec = max_arg
            lte_spec = None
        else:
            lt_spec = None
            lte_spec = max_arg

        expected_error_msg = None
        error_type = ValueError
        if min_arg is not None and max_arg is not None:
            if gt_gte_arg == "gte" and lt_lte_arg == "lte":
                if max_arg < min_arg:
                    expected_error_msg = re.escape(
                        f"Expected {gt_gte_arg}={min_arg} to be <= {lt_lte_arg}={max_arg}."
                    )
            else:
                if max_arg <= min_arg:
                    expected_error_msg = re.escape(
                        f"Expected {gt_gte_arg}={min_arg} to be < {lt_lte_arg}={max_arg}."
                    )

        if (type_spec_arg is int) or (type_spec_arg is float):
            if max_arg is not None and not isinstance(max_arg, type_spec_arg):
                expected_error_msg = re.escape(
                    f"Expected {lt_lte_arg}={max_arg} to be of type {type_spec_arg}, got {type(max_arg).__name__}."
                )
                error_type = TypeError
            if min_arg is not None and not isinstance(min_arg, type_spec_arg):
                expected_error_msg = re.escape(
                    f"Expected {gt_gte_arg}={min_arg} to be of type {type_spec_arg}, got {type(min_arg).__name__}."
                )
                error_type = TypeError

        if expected_error_msg is not None:
            with pytest.raises(error_type, match=expected_error_msg):

                class MyClass:
                    val1 = NumValue(
                        type_spec=type_spec_arg,
                        gte=gte_spec,
                        gt=gt_spec,
                        lt=lt_spec,
                        lte=lte_spec,
                    )

                    def __init__(self, val1: int):
                        self.val1 = val1

            return

        ################################################################
        #
        ################################################################
        class MyClass:
            val1 = NumValue(
                type_spec=type_spec_arg,
                gte=gte_spec,
                gt=gt_spec,
                lt=lt_spec,
                lte=lte_spec,
            )

            def __init__(self, val1):
                self.val1 = val1

        if type_spec_arg is int:
            val_array = range(-4, 5)
        else:
            val_array = [i * 0.25 for i in range(-4, 20)]
        for val in val_array:
            expected_error_msg = None
            if max_arg is not None:
                if lt_lte_arg == "lt":
                    if max_arg <= val:
                        expected_error_msg = re.escape(
                            f"Expected value={val} to be < {max_arg}."
                        )
                else:
                    if max_arg < val:
                        expected_error_msg = re.escape(
                            f"Expected value={val} to be <= {max_arg}."
                        )
            if min_arg is not None:
                if gt_gte_arg == "gt":
                    if val <= min_arg:
                        expected_error_msg = re.escape(
                            f"Expected value={val} to be > {min_arg}."
                        )
                else:
                    if val < min_arg:
                        expected_error_msg = re.escape(
                            f"Expected value={val} to be >= {min_arg}."
                        )

            if expected_error_msg is not None:
                with pytest.raises(ValueError, match=expected_error_msg):
                    MyClass(val1=val)
            else:
                MyClass(val1=val)


########################################################################
# TestValidatorExamples
########################################################################
class TestValidatorExamples:
    """Test examples of Validator."""

    ####################################################################
    # test_validator_example1
    ####################################################################
    def test_validator_example1(self, capsys: Any) -> None:
        """Test validator example1.

        This example shows that instantiating class with good values
        will pass and bad values will be caught.

        Args:
            capsys: pytest fixture to capture print output

        """
        print("mainline entered")
        from scottbrian_utils.validator import NumValue

        class MyClass:
            val1 = NumValue(type_spec=int, gte=1, lte=5)

            def __init__(self, val1: int):
                self.val1 = val1

        my_class_a = MyClass(val1=1)  # OK

        expected_error_msg = re.escape("Expected value=0 to be >= 1.")
        with pytest.raises(ValueError, match=expected_error_msg):
            my_class_b = MyClass(val1=0)  # ValueError

        expected_error_msg = re.escape("Expected value=6 to be <= 5.")
        with pytest.raises(ValueError, match=expected_error_msg):
            my_class_c = MyClass(val1=6)  # ValueError

        expected_error_msg = re.escape(
            "Expected value='1' to be of type <class 'int'>."
        )
        with pytest.raises(TypeError, match=expected_error_msg):
            my_class_d = MyClass(val1="1")  # typedef: ignore

        expected_error_msg = re.escape(
            "Expected value=1.2 to be of type <class 'int'>."
        )
        with pytest.raises(TypeError, match=expected_error_msg):
            my_class_e = MyClass(val1=1.2)  # typedef: ignore

    ####################################################################
    # test_validator_example2
    ####################################################################
    def test_validator_example2(self, capsys: Any) -> None:
        """Test validator example2.

        This example shows that instantiating class with good values
        will pass and bad values will be caught.

        Args:
            capsys: pytest fixture to capture print output

        """
        print("mainline entered")
        from scottbrian_utils.validator import ChoseOne

        class MyClass:
            val1 = ChoseOne(type_spec=str, choices=("Good", "Bad", "Ugly"))

            def __init__(self, val1: str):
                self.val1 = val1

        my_class_a = MyClass(val1="Good")  # OK

        expected_error_msg = (
            "Expected value='Best' to be one of {['Good', 'Bad', 'Ugly']+}."
        )
        with pytest.raises(ValueError, match=expected_error_msg):
            my_class_b = MyClass(val1="Best")  # ValueError

        expected_error_msg = re.escape(f"Expected value=1 to be of type <class 'str'>.")
        with pytest.raises(TypeError, match=expected_error_msg):
            my_class_c = MyClass(val1=1)  # typedef: ignore TypeError

    ####################################################################
    # test_validator_example3
    ####################################################################
    def test_validator_example3(self, capsys: Any) -> None:
        """Test validator example3.

        This example shows that instantiating class with good values
        will pass and bad values will be caught.

        Args:
            capsys: pytest fixture to capture print output

        """
        print("mainline entered")

        class MyClass:
            val1 = True_False()

            def __init__(self, val1: bool):
                self.val1 = val1

        my_class_a1 = MyClass(val1=True)  # OK
        my_class_a2 = MyClass(val1=False)  # OK

        expected_error_msg = re.escape(
            "Expected type(value)=<class 'str'> to be of type <class 'bool'>."
        )
        with pytest.raises(TypeError, match=expected_error_msg):
            my_class_b = MyClass(val1="True")  # typedef: ignore TypeError

        expected_error_msg = re.escape(
            "Expected type(value)=<class 'int'> to be of type <class 'bool'>."
        )
        with pytest.raises(TypeError, match=expected_error_msg):
            my_class_b = MyClass(val1=1)  # typedef: ignore TypeError


########################################################################
# TestValidatorChoseOne
########################################################################
class TestValidatorChoseOne:
    """Test validator ChoseOne."""

    ####################################################################
    # test_validator_chose_one
    ####################################################################
    @pytest.mark.parametrize(
        "type_set_vals_arg",
        (
            (int, (-1, 3, 6, 0), (-2, -1, 0, 1, 2, 3, 4, 5, 6, 7)),
            (
                float,
                (-1.22, 0.0, 6.7, 3.4),
                (
                    -3.4,
                    -1.22,
                    -1.0,
                    0.0,
                    3.4,
                    3.5,
                ),
            ),
            (str, ("hi", "low", "big", "small"), ("hi", "hello", "big", "little")),
            (bool, (True, False), (True, False)),
        ),
    )
    def test_validator_chose_one(
        self, type_set_vals_arg: tuple[tuple[Any], tuple[Any], tuple[Any]]
    ) -> None:
        """Test validator chose one."""

        ################################################################
        # type=int
        ################################################################
        quote = "'" if type_set_vals_arg[0] is str else ""
        error_msg_insert = "{["
        for choice in type_set_vals_arg[1]:
            error_msg_insert += f"{quote}{str(choice)}{quote}, "
        error_msg_insert += "]+}."

        quote = "'" if type_set_vals_arg[0] is str else ""

        class MyClass:
            val1 = ChoseOne(
                type_spec=type_set_vals_arg[0], choices=type_set_vals_arg[1]
            )

            def __init__(self, val1: int):
                self.val1 = val1

        for choice in type_set_vals_arg[2]:
            if choice in type_set_vals_arg[1]:
                MyClass(val1=choice)  # OK
            else:
                expected_error_msg = (
                    re.escape(f"Expected value={quote}{choice}{quote} to be one of ")
                    + error_msg_insert
                )
                with pytest.raises(ValueError, match=expected_error_msg):
                    MyClass(val1=choice)  # typedef: ignore
