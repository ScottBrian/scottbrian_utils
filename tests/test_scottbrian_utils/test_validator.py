"""test_validator.py module."""

########################################################################
# Standard Library
########################################################################
import logging
import os
import re
from typing import Any

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
# TestUniqueTSExamples class
########################################################################
class TestValidatorExamples:
    """Test examples of UniqueTS."""

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
            val1 = NumValue(type=int, minvalue=1, maxvalue=5)

            def __init__(self, val1: int):
                self.val1 = val1

        my_class_a = MyClass(val1=1)  # OK

        expected_error_msg = "Expected value=0 to be no less than 1"
        with pytest.raises(ValueError, match=expected_error_msg):
            my_class_b = MyClass(val1=0)  # ValueError

        expected_error_msg = "Expected value=6 to be no greater than 5"
        with pytest.raises(ValueError, match=expected_error_msg):
            my_class_c = MyClass(val1=6)  # ValueError

        expected_error_msg = "Expected value='1' to be of type <class 'int'>"
        with pytest.raises(TypeError, match=expected_error_msg):
            my_class_d = MyClass(val1="1")  # typedef: ignore TypeError

        expected_error_msg = "Expected value=1.2 to be of type <class 'int'>"
        with pytest.raises(TypeError, match=expected_error_msg):
            my_class_e = MyClass(val1=1.2)  # typedef: ignore TypeError

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
            val1 = ChoseOne(type=str, choices=("Good", "Bad", "Ugly"))

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
            my_class_d = MyClass(val1=1)  # typedef: ignore TypeError

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
            my_class_d = MyClass(val1="True")  # typedef: ignore TypeError
