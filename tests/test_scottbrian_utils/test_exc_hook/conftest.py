"""conftest.py module for testing."""

########################################################################
# Standard Library
########################################################################
import re
import pytest

from typing import Any, cast, Generator

import logging

########################################################################
# Third Party
########################################################################

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
    monkeypatch: Any, request, caplog: pytest.LogCaptureFixture
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
        "ExcHook __enter__ new hook was set: self.old_hook=.+, self.new_hook="
        "<function ExcHook.mock_threading_excepthook at 0x[0-9A-F]+>"
    )
    log_ver.add_pattern(entry_log_msg, log_name="scottbrian_utils.exc_hook")
    try:
        with ExcHook(monkeypatch) as exc_hook:
            yield exc_hook
    except Exception as exc:
        print(exc)

    exit_log_msg = (
        "ExcHook __exit__ current hook threading.excepthook=<function "
        "ExcHook.mock_threading_excepthook at 0x[0-9A-F]+> will now be "
        "restored to self.old_hook=.+"
    )
    log_ver.add_pattern(exit_log_msg, log_name="scottbrian_utils.exc_hook")

    log_ver.test_msg("conftest exit")

    ################################################################
    # check log results
    ################################################################
    match_results = log_ver.get_match_results(
        caplog=caplog, which_records=["setup", "teardown"]
    )
    log_ver.print_match_results(match_results, print_matched=True)
    log_ver.verify_match_results(match_results)
