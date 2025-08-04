"""conftest.py module for testing."""

########################################################################
# Standard Library
########################################################################
import logging
import re
import threading
from typing import Generator, NamedTuple

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.exc_hook import ExcHook
from scottbrian_utils.log_verifier import LogVer

########################################################################
# logging
########################################################################
# logging.basicConfig(filename='MyLogFile.log',
#                     filemode='w',
#                     level=logging.DEBUG,
#                     format='%(asctime)s '
#                            '%(msecs)03d '
#                            '[%(levelname)8s] '
#                            '%(filename)s:'
#                            '%(funcName)s:'
#                            '%(lineno)d '
#                            '%(message)s')

logger = logging.getLogger(__name__)


class LogMsgPattern(NamedTuple):
    """NamedTuple for the request passed to conftest."""

    log_msg_pattern: str
    log_level: int = 10
    log_name: str = "scottbrian_utils.exc_hook"
    fullmatch: bool = True


class ThreadItem(NamedTuple):
    """NamedTuple for the request passed to conftest."""

    thread: threading.Thread
    event: threading.Event


class MarkerArgs(NamedTuple):
    """NamedTuple for the request passed to conftest."""

    exception: Exception
    log_msg_patterns: tuple[LogMsgPattern, ...] = ()
    thread_array: list[ThreadItem] = []


########################################################################
# thread_exc
#
# Usage:
# The thread_exc is an autouse fixture which means it does not need to
# be specified as an argument in the test case methods. If a thread
# fails, such as an assert error, then thread_exc will capture the error
# and raise it for the thread, and will also raise it during cleanup
# processing for the mainline to ensure the test case fails. Without
# thread_exc, any uncaptured thread failure will appear in the output,
# but the test case itself will not fail.
# Also, if you need to issue the thread error earlier, before cleanup,
# then specify thread_exc as an argument on the test method and then in
# mainline issue:
#     thread_exc.raise_exc_if_one()
#
# When the above is done, cleanup will not raise the error again.
#
########################################################################
@pytest.fixture(autouse=True)
def thread_exc(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    caplog: pytest.LogCaptureFixture,
) -> Generator["ExcHook", None, None]:
    """Instantiate and yield a ThreadExc for testing.

    Args:
        monkeypatch: pytest fixture used to modify code for testing
        request: for pytest
        caplog: pytest fixture for logging capturing

    Yields:
        a thread exception handler

    """
    log_ver = LogVer(log_name=__name__)

    log_ver.test_msg("conftest entry")

    entry_log_msg = (
        r"ExcHook __enter__ new hook was set: old_hook=.+, self.new_hook="
        r"functools.partial\(<function ExcHook.mock_threading_excepthook at "
        r"0x[0-9A-F]+>, <scottbrian_utils.exc_hook.ExcHook object at 0x[0-9A-F]+>\)"
    )
    log_ver.add_pattern(entry_log_msg, log_name="scottbrian_utils.exc_hook")

    # Test cases build the expected LogVer pattern for the log msg that
    # ExcHook __exit__ will issue when it calls raise_exc_if_one.
    # The test case uses pytest.mark.fixt_data to pass the msg to this
    # thread_exc fixture which is doing the log verification for
    # the breakdown.
    my_exc_type = Exception(r".+")
    expected_error_occurred = True

    marker = request.node.get_closest_marker("fixt_data")
    thread_array = []
    if marker is not None:
        expected_error_occurred = False
        marker_args: MarkerArgs = marker.args[0]
        my_exc_type = marker_args.exception
        for log_pattern in marker_args.log_msg_patterns:
            log_ver.add_pattern(
                log_pattern.log_msg_pattern,
                level=log_pattern.log_level,
                log_name=log_pattern.log_name,
                fullmatch=log_pattern.fullmatch,
            )
        thread_array = marker_args.thread_array

    try:
        with ExcHook(monkeypatch) as exc_hook:
            yield exc_hook
    except type(my_exc_type) as exc:
        re.fullmatch(str(my_exc_type), str(exc))
        expected_error_occurred = True
    finally:
        if not expected_error_occurred:
            print(f"\n*** failed to catch expected error: {my_exc_type}")
        for thread_item in thread_array:
            thread_item.event.set()
            thread_item.thread.join(timeout=5)

    log_ver.test_msg("conftest exit")

    ################################################################
    # check log results
    ################################################################
    match_results = log_ver.get_match_results(
        caplog=caplog, which_records=["setup", "teardown"]
    )
    log_ver.print_match_results(match_results, print_matched=True)
    log_ver.verify_match_results(match_results)
