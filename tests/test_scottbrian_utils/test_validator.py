"""test_validator.py module."""

########################################################################
# Standard Library
########################################################################
import logging
import os
import re
from typing import Any, TypeAlias, Union

import pytest

########################################################################
# Third Party
########################################################################
########################################################################
# Local
########################################################################
from scottbrian_utils.testlib_verifier import verify_lib
from scottbrian_utils.validator import NumValue

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
class TestValidator:
    """Test validator."""

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

        expected_error_msg = "Expected value='1' to be of type <class 'int'>"
        with pytest.raises(TypeError, match=expected_error_msg):
            MyClass(val1="1")  # typedef: ignore

        expected_error_msg = "Expected value=1.2 to be of type <class 'int'>"
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

        expected_error_msg = "Expected value=-999 to be of type <class 'float'>"
        with pytest.raises(TypeError, match=expected_error_msg):
            MyClass(val1=-999)  # typedef: ignore

        expected_error_msg = "Expected value='1' to be of type <class 'float'>"
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

        expected_error_msg = "Expected value='1' to be of type int | float"
        with pytest.raises(TypeError, match=expected_error_msg):
            MyClass(val1="1")  # typedef: ignore

        ################################################################
        # type=str
        ################################################################
        expected_error_msg = f"Invalid type specification: str. Only int, float, or int | float are allowed."
        with pytest.raises(TypeError, match=expected_error_msg):

            class MyClass:
                val1 = NumValue(type_spec=str)

                def __init__(self, val1: float):
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
                expected_error_msg = f"Expected value={val} to be >= {gte_arg}"
                with pytest.raises(ValueError, match=expected_error_msg):
                    MyClass(val1=val)
            else:
                MyClass(val1=val)

    ####################################################################
    # test_validator_numvalue_int_gt
    ####################################################################
    restriction_vals = (
        None,
        -3.0,
        -3,
        -2.5,
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
        2.5,
        3.0,
        3,
    )

    @pytest.mark.parametrize("type_spec_arg", (int, float, int | float, IntFloat))
    @pytest.mark.parametrize("gt_gte_arg", ('gt', 'gte'))
    @pytest.mark.parametrize("lt_lte_arg", ('lt', 'lte'))
    @pytest.mark.parametrize("min_arg", restriction_vals)
    @pytest.mark.parametrize("max_arg", restriction_vals)
    def test_validator_numvalue_int_gt(
        self,
        type_spec_arg: type,
        gt_gte_arg: str,
        min_arg: int | float,
        max_arg: int | float,
    ) -> None:
        """Test validator NumValue int gt.

        Test NumValue with int values.

        """
        def check_compatability(type_spec, gt_gte_spec, lt_lte_spec, min_spec, max_spec):
            if isinstance(type_spec_arg, :
            if min_arg is not None and isinstance(min_arg, float):
                exp_error = 'ValueError'
                exp_error_msg = f"Expected {value=} to be of type {self._type_spec}, got {type(value).__name__}"

        ################################################################
        # type=int
        ################################################################
        class MyClass:
            val1 = NumValue(
                type_spec=int, gte=gte_arg, gt=gt_arg, lt=lt_arg, lte=lte_arg
            )

            def __init__(self, val1: int):
                self.val1 = val1

        for val in range(-4, 5):
            if val <= gt_arg:
                expected_error_msg = f"Expected value={val} to be > {gt_arg}"
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

        expected_error_msg = "Expected value=0 to be >= 1"
        with pytest.raises(ValueError, match=expected_error_msg):
            my_class_b = MyClass(val1=0)  # ValueError

        expected_error_msg = "Expected value=6 to be <= 5"
        with pytest.raises(ValueError, match=expected_error_msg):
            my_class_c = MyClass(val1=6)  # ValueError

        expected_error_msg = "Expected value='1' to be of type <class 'int'>"
        with pytest.raises(TypeError, match=expected_error_msg):
            my_class_d = MyClass(val1="1")  # typedef: ignore

        expected_error_msg = "Expected value=1.2 to be of type <class 'int'>"
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
            r"Expected value='Best' to be one of {['Good', 'Bad', 'Ugly']+}"
        )
        with pytest.raises(ValueError, match=expected_error_msg):
            my_class_b = MyClass(val1="Best")  # ValueError

        expected_error_msg = f"Expected value=1 to be of type <class 'str'>"
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
        from scottbrian_utils.validator import True_False

        class MyClass:
            val1 = True_False()

            def __init__(self, val1: bool):
                self.val1 = val1

        my_class_a1 = MyClass(val1=True)  # OK
        my_class_a2 = MyClass(val1=False)  # OK

        expected_error_msg = re.escape(
            "Expected type(value)=<class 'str'> to be of type <class 'bool'>"
        )
        with pytest.raises(TypeError, match=expected_error_msg):
            my_class_b = MyClass(val1="True")  # typedef: ignore TypeError

        expected_error_msg = re.escape(
            "Expected type(value)=<class 'int'> to be of type <class 'bool'>"
        )
        with pytest.raises(TypeError, match=expected_error_msg):
            my_class_b = MyClass(val1=1)  # typedef: ignore TypeError
