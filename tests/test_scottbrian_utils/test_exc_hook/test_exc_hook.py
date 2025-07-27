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
from scottbrian_utils.exc_hook import ExcHook
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
        """Test exc_hook assert error."""
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
    # build the LogVer pattern for the exception message that will be
    # issued by the ExcHook __exit__ and pass it to the thread_exc
    # fixture in conftest via the pytest.mark.fixt_data construct
    exception_type = AssertionError
    exception_msg = (
        r"Test case excepthook: args.exc_type=<class 'AssertionError'>, "
        r"args.exc_value=AssertionError\(\'assert \(3 \* 5\) == 16\'\), "
        r"args.exc_traceback=<traceback object at 0x[0-9A-F]+>, "
        r"args.thread=<Thread\(Thread-[0-9]+ \(f1\), started [0-9]+\)>"
    )
    exc_hook_log_msg = (
        rf"caller exc_hook.py::ExcHook.__exit__:[0-9]+ is raising "
        rf'Exception: exc_err_msg="{exception_msg}"'
    )

    @pytest.mark.fixt_data((exception_type, exc_hook_log_msg))
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
        monkeypatch: pytest.MonkeyPatch,
        thread_exc,
    ) -> None:
        """test_exc_hook_thread_raise_error."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        def f1() -> None:
            """F1 thread."""
            var1 = 1 / 0

        f1_thread = threading.Thread(target=f1)

        f1_thread.start()

        f1_thread.join()

        exception_msg = (
            r"Test case excepthook: args.exc_type=<class 'ZeroDivisionError'>, "
            r"args.exc_value=ZeroDivisionError\('division by zero'\), "
            r"args.exc_traceback=<traceback object at 0x[0-9A-F]+>, "
            r"args.thread=<Thread\(Thread-[0-9]+ \(f1\), started [0-9]+\)>"
        )

        with pytest.raises(ZeroDivisionError, match=exception_msg):
            thread_exc.raise_exc_if_one(exception=ZeroDivisionError)

        log_ver.test_msg("mainline exit")

        exc_hook_log_msg = (
            rf"caller test_exc_hook.py::TestExcHookBasic.test_exc_hook_thread_raise_error:[0-9]+ is raising Exception: "
            rf'exc_err_msg="{exception_msg}"'
        )

        log_ver.add_pattern(
            exc_hook_log_msg, log_name="scottbrian_utils.exc_hook", fullmatch=True
        )

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)
