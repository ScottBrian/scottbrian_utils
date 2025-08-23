"""test_unique_ts.py module."""

########################################################################
# Standard Library
########################################################################
import inspect
import logging
import os
import sys
from typing import Any

########################################################################
# Third Party
########################################################################


########################################################################
# Local
########################################################################
from scottbrian_utils.src_verifier import verify_source
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
# TestUniqueTStampCorrectSource
########################################################################
class TestUniqueTStampCorrectSource:
    """Verify that we are testing with correctly built code."""

    ####################################################################
    # test_unique_ts_correct_source
    ####################################################################
    def test_unique_ts_correct_source(self) -> None:
        """Test unique_ts correct source."""
        if "TOX_ENV_NAME" in os.environ:
            verify_source(obj_to_check=UniqueTStamp)


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

        # set the following four lines
        library = "C:\\Users\\Tiger\\PycharmProjects\\"
        project = "scottbrian_utils"
        py_file = "unique_ts.py"
        class_to_use = UniqueTS

        file_prefix = (
            f"{library}{project}\\.tox"
            f"\\py{sys.version_info.major}{sys.version_info.minor}-"
        )
        file_suffix = f"\\Lib\\site-packages\\{project}\\{py_file}"

        pytest_run = f"{file_prefix}pytest{file_suffix}"
        coverage_run = f"{file_prefix}coverage{file_suffix}"

        actual = inspect.getsourcefile(class_to_use)
        assert (actual == pytest_run) or (actual == coverage_run)

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
