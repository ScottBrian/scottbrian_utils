"""test_unique_ts.py module."""

########################################################################
# Standard Library
########################################################################
import inspect
import logging
import sys
from typing import Any

########################################################################
# Third Party
########################################################################


########################################################################
# Local
########################################################################
from scottbrian_utils.unique_ts import UniqueTS, UniqueTStamp


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
class ErrorTstUniqueTS(Exception):
    """Base class for exception in this module."""

    pass


########################################################################
# TestUniqueTSExamples class
########################################################################
class TestUniqueTSExamples:
    """Test examples of UniqueTS."""

    ####################################################################
    # test_unique_ts_example1
    ####################################################################
    def test_unique_ts_example1(self, capsys: Any) -> None:
        """Test unique time stamp example1.

        This example shows that obtaining two time stamps in quick
        succession using get_unique_time_ts() guarantees they will be
        unique.

        Args:
            capsys: pytest fixture to capture print output

        """
        print("mainline entered")
        from scottbrian_utils.unique_ts import UniqueTS, UniqueTStamp

        first_time_stamp: UniqueTStamp = UniqueTS.get_unique_ts()
        second_time_stamp: UniqueTStamp = UniqueTS.get_unique_ts()

        print(second_time_stamp > first_time_stamp)

        print("mainline exiting")

        expected_result = "mainline entered\n"
        expected_result += "True\n"
        expected_result += "mainline exiting\n"

        captured = capsys.readouterr().out

        assert captured == expected_result


########################################################################
# TestUniqueTSBasic class
########################################################################
class TestUniqueTSBasic:
    """Test basic functions of UniqueTS."""

    ####################################################################
    # test_unique_time_stamp_correct_source
    ####################################################################
    def test_unique_time_stamp_correct_source(self) -> None:
        """Test unique time stamp correct source."""
        print("\nmainline entered")
        print(f"{inspect.getsourcefile(UniqueTS)=}")
        if sys.version_info.minor == 9:
            exp1 = (
                "C:\\Users\\Tiger\\PycharmProjects\\scottbrian_utils\\.tox"
                "\\py39-pytest\\lib\\site-packages\\scottbrian_utils"
                "\\unique_ts.py"
            )
            exp2 = (
                "C:\\Users\\Tiger\\PycharmProjects\\scottbrian_utils\\.tox"
                "\\py39-coverage\\lib\\site-packages\\scottbrian_utils"
                "\\unique_ts.py"
            )
        elif sys.version_info.minor == 10:
            exp1 = (
                "C:\\Users\\Tiger\\PycharmProjects\\scottbrian_utils\\.tox"
                "\\py310-pytest\\lib\\site-packages\\scottbrian_utils"
                "\\unique_ts.py"
            )
            exp2 = (
                "C:\\Users\\Tiger\\PycharmProjects\\scottbrian_utils\\.tox"
                "\\py310-coverage\\lib\\site-packages\\scottbrian_utils"
                "\\unique_ts.py"
            )
        elif sys.version_info.minor == 11:
            exp1 = (
                "C:\\Users\\Tiger\\PycharmProjects\\scottbrian_utils\\.tox"
                "\\py311-pytest\\Lib\\site-packages\\scottbrian_utils"
                "\\unique_ts.py"
            )
            exp2 = (
                "C:\\Users\\Tiger\\PycharmProjects\\scottbrian_utils\\.tox"
                "\\py311-coverage\\Lib\\site-packages\\scottbrian_utils"
                "\\unique_ts.py"
            )
        elif sys.version_info.minor == 12:
            exp1 = (
                "C:\\Users\\Tiger\\PycharmProjects\\scottbrian_utils\\.tox"
                "\\py312-pytest\\Lib\\site-packages\\scottbrian_utils"
                "\\unique_ts.py"
            )
            exp2 = (
                "C:\\Users\\Tiger\\PycharmProjects\\scottbrian_utils\\.tox"
                "\\py312-coverage\\Lib\\site-packages\\scottbrian_utils"
                "\\unique_ts.py"
            )
        else:
            exp1 = ""
            exp2 = ""

        actual = inspect.getsourcefile(UniqueTS)
        assert (actual == exp1) or (actual == exp2)
        print("mainline exiting")

    ####################################################################
    # test_unique_ts_case1a
    ####################################################################
    def test_unique_ts_case1a(self) -> None:
        """Test unique_ts case1a."""
        print("mainline entered")
        first_time_stamp: UniqueTStamp = UniqueTS.get_unique_ts()
        second_time_stamp: UniqueTStamp = UniqueTS.get_unique_ts()

        assert second_time_stamp > first_time_stamp

        print("mainline exiting")
