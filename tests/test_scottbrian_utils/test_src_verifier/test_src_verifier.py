"""test_src_verifier.py module."""

########################################################################
# Standard Library
########################################################################
import logging

import pytest
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
        """Test simple case with no error."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")
        library = "C:\\Users\\Tiger\\PycharmProjects\\"
        project = "scottbrian_utils"
        py_file = "src_verifier.py"
        class_to_use = verify_source
        verify_source(
            library=library,
            project=project,
            py_file=py_file,
            obj_to_find=verify_source,
        )

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)
