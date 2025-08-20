"""test_src_verifier.py module."""

########################################################################
# Standard Library
########################################################################
import logging
import os
import pytest
import re
import sys
from typing import Any

########################################################################
# Third Party
########################################################################


########################################################################
# Local
########################################################################
from scottbrian_utils.log_verifier import LogVer
from scottbrian_utils.src_verifier import verify_source


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
class ErrorTestSrcVerifier(Exception):
    """Base class for exception in this module."""

    pass


########################################################################
# TestUniqueTSExamples class
########################################################################
class TestSrcVerifierExamples:
    """Test examples of UniqueTS."""

    ####################################################################
    # test_exc_hook_example1
    ####################################################################
    def test_src_verifier_example1(self, capsys: Any) -> None:
        """Test unique time stamp example1.

        This example shows that obtaining two time stamps in quick
        succession using get_unique_time_ts() guarantees they will be
        unique.

        Args:
            capsys: pytest fixture to capture print output

        """
        print("mainline entered")

        print("mainline exiting")


########################################################################
# TestUniqueTSBasic class
########################################################################
class TestSrcVerifierBasic:
    """Test basic functions of UniqueTS."""

    ####################################################################
    # test_src_verifier_no_error
    ####################################################################
    def test_src_verifier_no_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test with default str_to_check."""

        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        if "TOX_ENV_NAME" in os.environ:
            str_to_check = ".tox"
            exp_src_path = (
                "C:/Users/Tiger/PycharmProjects/scottbrian_utils/"
                f".tox/py{sys.version_info.major}{sys.version_info.minor}"
                f"-(pytest|coverage)/Lib/site-packages/scottbrian_utils/src_verifier.py"
            )
        else:
            str_to_check = "src/scottbrian_utils/src_verifier.py"
            exp_src_path = (
                "C:/Users/Tiger/PycharmProjects/scottbrian_utils/"
                "src/scottbrian_utils/src_verifier.py"
            )

        expected_log_pattern = (
            "obj_to_check=<function verify_source at 0x[0-9A-F]+>, "
            f"str_to_check='{str_to_check}', "
            f"src_path='{exp_src_path}'"
        )

        actual_src_path = verify_source(
            obj_to_check=verify_source, str_to_check=str_to_check
        )

        log_ver.add_pattern(
            expected_log_pattern,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        assert re.fullmatch(exp_src_path, actual_src_path)

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_src_verifier_no_error2
    ####################################################################
    def test_src_verifier_no_error2(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test with str_to_check specified same as default."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        if "TOX_ENV_NAME" in os.environ:
            str_to_check = ".tox"
            exp_src_path = (
                "C:/Users/Tiger/PycharmProjects/scottbrian_utils/"
                f".tox/py{sys.version_info.major}{sys.version_info.minor}"
                f"-(pytest|coverage)/Lib/site-packages/scottbrian_utils/src_verifier.py"
            )
        else:
            str_to_check = "src/scottbrian_utils/src_verifier.py"
            exp_src_path = (
                "C:/Users/Tiger/PycharmProjects/scottbrian_utils/"
                "src/scottbrian_utils/src_verifier.py"
            )

        actual_src_path = verify_source(
            obj_to_check=verify_source, str_to_check=str_to_check
        )

        expected_log_pattern = (
            "obj_to_check=<function verify_source at 0x[0-9A-F]+>, "
            f"str_to_check='{str_to_check}', "
            f"src_path='{exp_src_path}'"
        )

        log_ver.add_pattern(
            expected_log_pattern,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        assert re.fullmatch(exp_src_path, actual_src_path)

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)
