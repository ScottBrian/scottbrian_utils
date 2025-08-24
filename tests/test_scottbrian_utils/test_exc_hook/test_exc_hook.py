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
from scottbrian_utils.exc_hook import ExcHook
from .conftest import LogMsgPattern, MarkerArgs, ThreadItem


########################################################################
# logger
########################################################################
logger = logging.getLogger(__name__)

########################################################################
# type aliases
########################################################################

thread_array: list[ThreadItem] = []


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

        def thread1() -> None:
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
    exception_pattern = (
        r"Test case excepthook: args.exc_type=<class 'AssertionError'>, "
        r"args.exc_value=AssertionError\(\'assert \(3 \* 5\) == 16\'\), "
        r"args.exc_traceback=<traceback object at 0x[0-9A-F]+>, "
        r"args.thread=<Thread\(Thread-[0-9]+ \(f1\), started [0-9]+\)>"
    )
    log_msg_pattern = LogMsgPattern(
        r"caller exc_hook.py::ExcHook.__exit__:[0-9]+ is raising "
        rf'Exception: "{exception_pattern}"'
    )

    @pytest.mark.fixt_data(
        MarkerArgs(
            exception=AssertionError(exception_pattern),
            log_msg_patterns=(log_msg_pattern,),
        )
    )
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
    # test_exc_hook_thread_unhandled_zero_divide_error
    ####################################################################
    # build the LogVer pattern for the exception message that will be
    # issued by the ExcHook __exit__ and pass it to the thread_exc
    # fixture in conftest via the pytest.mark.fixt_data construct
    exception_pattern = (
        r"Test case excepthook: args.exc_type=<class 'ZeroDivisionError'>, "
        r"args.exc_value=ZeroDivisionError\('division by zero'\), "
        r"args.exc_traceback=<traceback object at 0x[0-9A-F]+>, "
        r"args.thread=<Thread\(Thread-[0-9]+ \(f1\), started [0-9]+\)>"
    )
    log_msg_pattern = LogMsgPattern(
        r"caller exc_hook.py::ExcHook.__exit__:[0-9]+ is raising "
        rf'Exception: "{exception_pattern}"'
    )

    @pytest.mark.fixt_data(
        MarkerArgs(
            exception=ZeroDivisionError(exception_pattern),
            log_msg_patterns=(log_msg_pattern,),
        )
    )
    def test_exc_hook_thread_unhandled_zero_divide_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """test exc_hook thread unhandled divide by zero error."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        def f1() -> None:
            """F1 thread."""
            var1 = 3
            var2 = 0
            var1 / var2

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
    # test_exc_hook_thread_raise_assert_error
    ####################################################################
    def test_exc_hook_thread_raise_assert_error(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
        thread_exc: ExcHook,
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

        exception_msg = (
            r"Test case excepthook: args.exc_type=<class 'AssertionError'>, "
            r"args.exc_value=AssertionError\(\'assert \(3 \* 5\) == 16\'\), "
            r"args.exc_traceback=<traceback object at 0x[0-9A-F]+>, "
            r"args.thread=<Thread\(Thread-[0-9]+ \(f1\), started [0-9]+\)>"
        )

        with pytest.raises(AssertionError, match=exception_msg):
            thread_exc.raise_exc_if_one()

        log_ver.test_msg("mainline exit")

        exc_hook_log_msg = (
            r"caller test_exc_hook.py::TestExcHookBasic."
            r"test_exc_hook_thread_raise_assert_error:[0-9]+ is "
            rf'raising Exception: "{exception_msg}"'
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

    ####################################################################
    # test_exc_hook_thread_raise_zero_divide_error
    ####################################################################
    def test_exc_hook_thread_raise_zero_divide_error(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
        thread_exc: ExcHook,
    ) -> None:
        """test_exc_hook_thread_raise_error."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        def f1() -> None:
            """F1 thread."""
            var1 = 1 / 0
            print(var1)

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
            thread_exc.raise_exc_if_one()

        log_ver.test_msg("mainline exit")

        exc_hook_log_msg = (
            r"caller test_exc_hook.py::TestExcHookBasic."
            r"test_exc_hook_thread_raise_zero_divide_error:[0-9]+ is "
            rf'raising Exception: "{exception_msg}"'
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

    ####################################################################
    # drive_threads_still_running_error
    ####################################################################
    def drive_threads_still_running_error(
        self,
        thread_array: list[ThreadItem],
        caplog: pytest.LogCaptureFixture,
        num_threads: int,
    ) -> None:
        """test exc_hook one thread still running error."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        def f1() -> None:
            """F1 thread."""
            f1_event.set()
            f1_event_exit.wait()

        def f2() -> None:
            """F2 thread."""
            f2_event.set()
            f2_event_exit.wait()

        def f3() -> None:
            """F2 thread."""
            f3_event.set()
            f3_event_exit.wait()

        f1_event = threading.Event()
        f1_event_exit = threading.Event()
        f2_event = threading.Event()
        f2_event_exit = threading.Event()
        f3_event = threading.Event()
        f3_event_exit = threading.Event()

        f1_thread = threading.Thread(target=f1)
        f2_thread = threading.Thread(target=f2)
        f3_thread = threading.Thread(target=f3)

        # start each thread one at a time and wait to ensure it was
        # started and got control so that we can control the assigned
        # thread number
        f1_thread.start()
        f1_event.wait()

        f2_thread.start()
        f2_event.wait()

        f3_thread.start()
        f3_event.wait()

        if num_threads == 1:
            thread_array.append(ThreadItem(thread=f1_thread, event=f1_event_exit))

            f2_event_exit.set()
            f2_thread.join(timeout=5)

            f3_event_exit.set()
            f3_thread.join(timeout=5)
        elif num_threads == 2:
            thread_array.append(ThreadItem(thread=f1_thread, event=f1_event_exit))
            thread_array.append(ThreadItem(thread=f2_thread, event=f2_event_exit))

            f3_event_exit.set()
            f3_thread.join(timeout=5)
        else:
            thread_array.append(ThreadItem(thread=f1_thread, event=f1_event_exit))
            thread_array.append(ThreadItem(thread=f2_thread, event=f2_event_exit))
            thread_array.append(ThreadItem(thread=f3_thread, event=f3_event_exit))

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_exc_hook_one_thread_still_running_error
    ####################################################################
    # build the LogVer pattern for the exception message that will be
    # issued by the ExcHook __exit__ and pass it to the thread_exc
    # fixture in conftest via the pytest.mark.fixt_data construct
    exc_hook_main_thread_log_pattern = LogMsgPattern(
        r"active thread 0: <_MainThread\(MainThread, started [0-9]+\)>"
    )
    exc_hook_f1_thread_log_pattern = LogMsgPattern(
        r"active thread 1: <Thread\(Thread-[0-9]+ \(f1\), started [0-9]+\)>"
    )
    exc_hook_f2_thread_log_pattern = LogMsgPattern(
        r"active thread 2: <Thread\(Thread-[0-9]+ \(f2\), started [0-9]+\)>"
    )
    exc_hook_f3_thread_log_pattern = LogMsgPattern(
        r"active thread 3: <Thread\(Thread-[0-9]+ \(f3\), started [0-9]+\)>"
    )
    runtime_exception_pattern = "1 thread failed to complete"
    log_msg_pattern = LogMsgPattern(
        log_msg_pattern=runtime_exception_pattern, log_level=10
    )

    @pytest.mark.fixt_data(
        MarkerArgs(
            exception=RuntimeError(runtime_exception_pattern),
            log_msg_patterns=(
                log_msg_pattern,
                exc_hook_main_thread_log_pattern,
                exc_hook_f1_thread_log_pattern,
            ),
            thread_array=thread_array,
        )
    )
    def test_exc_hook_one_thread_still_running_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """test exc_hook one thread still running error."""
        thread_array.clear()
        self.drive_threads_still_running_error(
            thread_array, caplog=caplog, num_threads=1
        )

    ####################################################################
    # test_exc_hook_two_threads_still_running_error
    ####################################################################
    runtime_exception_pattern = "2 threads failed to complete"
    log_msg_pattern = LogMsgPattern(
        log_msg_pattern=runtime_exception_pattern, log_level=10
    )

    @pytest.mark.fixt_data(
        MarkerArgs(
            exception=RuntimeError(runtime_exception_pattern),
            log_msg_patterns=(
                log_msg_pattern,
                exc_hook_main_thread_log_pattern,
                exc_hook_f1_thread_log_pattern,
                exc_hook_f2_thread_log_pattern,
            ),
            thread_array=thread_array,
        )
    )
    def test_exc_hook_two_threads_still_running_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """test exc_hook two threads still running error."""
        thread_array.clear()
        self.drive_threads_still_running_error(
            thread_array, caplog=caplog, num_threads=2
        )

    ####################################################################
    # test_exc_hook_three_threads_still_running_error
    ####################################################################
    runtime_exception_pattern = "3 threads failed to complete"
    log_msg_pattern = LogMsgPattern(
        log_msg_pattern=runtime_exception_pattern, log_level=10
    )

    @pytest.mark.fixt_data(
        MarkerArgs(
            exception=RuntimeError(runtime_exception_pattern),
            log_msg_patterns=(
                log_msg_pattern,
                exc_hook_main_thread_log_pattern,
                exc_hook_f1_thread_log_pattern,
                exc_hook_f2_thread_log_pattern,
                exc_hook_f3_thread_log_pattern,
            ),
            thread_array=thread_array,
        )
    )
    def test_exc_hook_three_threads_still_running_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """test exc_hook one thread still running error."""
        thread_array.clear()
        self.drive_threads_still_running_error(
            thread_array, caplog=caplog, num_threads=3
        )

    ####################################################################
    # test_exc_hook_replaced_error
    ####################################################################
    runtime_exception_pattern = (
        "ExcHook __exit__ detected that threading.excepthook does not contain "
        "the expected mock hook set by the ExcHook __entry__ method. "
        r"Expected hook: self.new_hook=functools.partial\(<function "
        "ExcHook.mock_threading_excepthook at 0x[0-9A-F]+>, "
        r"<scottbrian_utils.exc_hook.ExcHook object at 0x[0-9A-F]+>\) "
        "threading.excepthook: .+"
    )
    log_msg_pattern = LogMsgPattern(
        log_msg_pattern=runtime_exception_pattern, log_level=40
    )

    @pytest.mark.fixt_data(
        MarkerArgs(
            exception=RuntimeError(runtime_exception_pattern),
            log_msg_patterns=(log_msg_pattern,),
        )
    )
    def test_exc_hook_replaced_error(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
        thread_exc: ExcHook,
    ) -> None:
        """test_exc_hook_thread_raise_error."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        threading.excepthook = lambda x: "this is a bad hook"

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)
