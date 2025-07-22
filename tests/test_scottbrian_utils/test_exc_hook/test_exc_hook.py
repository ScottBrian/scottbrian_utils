"""test_exc_hook.py module."""

########################################################################
# Standard Library
########################################################################
import logging
import re
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

        print("mainline exiting")


########################################################################
# TestUniqueTSBasic class
########################################################################
class TestExcHookBasic:
    """Test basic functions of UniqueTS."""

    ####################################################################
    # test_exc_hook_no_error
    ####################################################################
    def test_exc_hook_no_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test simple case with no error."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        var1 = 3
        var2 = 5
        assert var1 * var2 == 15

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_exc_hook_thread_no_error
    ####################################################################
    def test_exc_hook_thread_no_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test simple case with no error."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        def thread1():
            var1 = 3
            var2 = 5
            assert var1 * var2 == 15

        a_thread = threading.Thread(target=thread1)
        a_thread.start()
        a_thread.join()

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_exc_hook_assert_error
    ####################################################################
    def test_exc_hook_handled_assert_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test exc_hook case1a."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        var1 = 3
        var2 = 5
        with pytest.raises(AssertionError):
            assert var1 * var2 == 16

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_exc_hook_thread_handled_assert_error
    ####################################################################
    def test_exc_hook_thread_handled_assert_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test exc_hook case1a."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        def f1() -> None:
            """F1 thread."""
            var1 = 3
            var2 = 5
            with pytest.raises(AssertionError):
                assert var1 * var2 == 16

        f1_thread = threading.Thread(target=f1)
        f1_thread.start()
        f1_thread.join()

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_exc_hook_thread_unhandled_assert_error
    ####################################################################
    def test_exc_hook_thread_unhandled_assert_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """test_exc_hook_thread_unhandled_assert_error."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        def f1() -> None:
            """F1 thread."""
            var1 = 3
            var2 = 5
            assert var1 * var2 == 16

        f1_thread = threading.Thread(target=f1)
        f1_thread.start()
        f1_thread.join()

        log_ver.test_msg("mainline exit")

        exc_hook_log_msg_1 = (
            r"Test case excepthook: args.exc_type=<class 'AssertionError'>, "
            r"args.exc_value=AssertionError\(\'assert \(3 \* 5\) == 16\'\), "
            r"args.exc_traceback=<traceback object at 0x[0-9A-F]+>, "
            r"args.thread=<Thread\(Thread-[0-9]+ \(f1\), started [0-9]{5,6}\)>"
        )
        log_ver.add_pattern(
            exc_hook_log_msg_1, log_name="scottbrian_utils.exc_hook", fullmatch=True
        )
        exc_hook_log_msg_2 = (
            r"exception caught for thread: <Thread\(Thread-[0-9]+ \(f1\), "
            r"started [0-9]{5,6}\)>"
        )
        log_ver.add_pattern(
            exc_hook_log_msg_2, log_name="root", level=40, fullmatch=True
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_exc_hook_raise_error
    ####################################################################
    def test_exc_hook_raise_error(
        self,
        caplog: pytest.LogCaptureFixture,
        thread_exc,
    ) -> None:
        """test_exc_hook_raise_error."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        thread_exc.raise_exc_if_one()

        log_ver.test_msg("mainline exit")

        exc_hook_log_msg_1 = (
            r"Test case excepthook: args.exc_type=<class 'AssertionError'>, "
            r"args.exc_value=AssertionError\(\'assert \(3 \* 5\) == 16\'\), "
            r"args.exc_traceback=<traceback object at 0x[0-9A-F]+>, "
            r"args.thread=<Thread\(Thread-[0-9]+ \(f1\), started [0-9]{5,6}\)>"
        )
        # log_ver.add_pattern(
        #     exc_hook_log_msg_1, log_name="scottbrian_utils.exc_hook", fullmatch=True
        # )
        exc_hook_log_msg_2 = (
            r"exception caught for thread: <Thread\(Thread-[0-9]+ \(f1\), "
            r"started [0-9]{5,6}\)>"
        )
        # log_ver.add_pattern(
        #     exc_hook_log_msg_2, log_name="root", level=40, fullmatch=True
        # )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_exc_hook_thread_raise_error
    ####################################################################
    def test_exc_hook_thread_raise_error(
        self,
        caplog: pytest.LogCaptureFixture,
        thread_exc,
    ) -> None:
        """test_exc_hook_thread_raise_error."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        def f1() -> None:
            """F1 thread."""
            var1 = 3
            var2 = 5
            assert var1 * var2 == 16

        f1_thread = threading.Thread(target=f1)
        f1_thread.start()
        f1_thread.join()

        log_ver.test_msg("mainline exit")

        exc_hook_log_msg_1 = (
            r"Test case excepthook: args.exc_type=<class 'AssertionError'>, "
            r"args.exc_value=AssertionError\(\'assert \(3 \* 5\) == 16\'\), "
            r"args.exc_traceback=<traceback object at 0x[0-9A-F]+>, "
            r"args.thread=<Thread\(Thread-[0-9]+ \(f1\), started [0-9]{5,6}\)>"
        )
        log_ver.add_pattern(
            exc_hook_log_msg_1, log_name="scottbrian_utils.exc_hook", fullmatch=True
        )
        exc_hook_log_msg_2 = (
            r"exception caught for thread: <Thread\(Thread-[0-9]+ \(f1\), "
            r"started [0-9]{5,6}\)>"
        )
        log_ver.add_pattern(
            exc_hook_log_msg_2, log_name="root", level=40, fullmatch=True
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)
