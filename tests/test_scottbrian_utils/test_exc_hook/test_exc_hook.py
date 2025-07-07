"""test_exc_hook.py module."""

########################################################################
# Standard Library
########################################################################
import logging
import threading

import pytest
from typing import Any

########################################################################
# Third Party
########################################################################


########################################################################
# Local
########################################################################
from scottbrian_utils.log_verifier import LogVer

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
class ErrorTestExcHook(Exception):
    """Base class for exception in this module."""

    pass


########################################################################
# TestUniqueTSExamples class
########################################################################
class TestExcHookExamples:
    """Test examples of UniqueTS."""

    ####################################################################
    # test_exc_hook_example1
    ####################################################################
    def test_exc_hook_example1(self, capsys: Any) -> None:
        """Test unique time stamp example1.

        This example shows that obtaining two time stamps in quick
        succession using get_unique_time_ts() guarantees they will be
        unique.

        Args:
            capsys: pytest fixture to capture print output

        """
        print("mainline entered")
        from scottbrian_utils.exc_hook import UniqueTS, UniqueTStamp

        first_time_stamp: UniqueTStamp = UniqueTS.get_exc_hook()
        second_time_stamp: UniqueTStamp = UniqueTS.get_exc_hook()

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
class TestExcHookBasic:
    """Test basic functions of UniqueTS."""

    ####################################################################
    # test_exc_hook_no_error
    ####################################################################
    def test_exc_hook_no_error(self) -> None:
        """Test simple case with no error."""

        var1 = 3
        var2 = 5
        assert var1 * var2 == 15

    ####################################################################
    # test_exc_hook_thread_no_error
    ####################################################################
    def test_exc_hook_thread_no_error(self) -> None:
        """Test simple case with no error."""

        def thread1():
            var1 = 3
            var2 = 5
            assert var1 * var2 == 15

        a_thread = threading.Thread(target=thread1)
        a_thread.start()
        a_thread.join()

    ####################################################################
    # test_exc_hook_assert_error
    ####################################################################
    def test_exc_hook_assert_error(self) -> None:
        """Test exc_hook case1a."""
        print("mainline entered")

        var1 = 3
        var2 = 5
        with pytest.raises(AssertionError):
            assert var1 * var2 == 16

        print("mainline exiting")

    ####################################################################
    # test_exc_hook_thread_handled_assert_error
    ####################################################################
    def test_exc_hook_thread_handled_assert_error(self) -> None:
        """Test exc_hook case1a."""
        print("mainline entered")

        def f1() -> None:
            """F1 thread."""
            var1 = 3
            var2 = 5
            with pytest.raises(AssertionError):
                assert var1 * var2 == 16

        f1_thread = threading.Thread(target=f1)
        f1_thread.start()
        f1_thread.join()

        print("mainline exiting")

    ####################################################################
    # test_exc_hook_thread_unhandled_assert_error
    ####################################################################
    def test_exc_hook_thread_unhandled_assert_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """test_exc_hook_thread_unhandled_assert_error."""
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        log_ver.test_msg("mainline entry")

        def f1() -> None:
            """F1 thread."""
            var1 = 3
            var2 = 5
            assert var1 * var2 == 16

        f1_thread = threading.Thread(target=f1)
        f1_thread.start()
        f1_thread.join()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)
