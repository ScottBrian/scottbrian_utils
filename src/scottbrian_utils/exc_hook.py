"""Module test_helpers

============
test_helpers
============

The *test_helpers* module provides classes to use during testing.

"""

########################################################################
# Standard Library
########################################################################
import threading
import traceback
from typing import Any
import logging

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################

logger = logging.getLogger(__name__)


########################################################################
# Thread exceptions
#
# Usage:
# The ExcHook thread_exc is used to intercept and emit details for
# thread failures during pytest testing. This will also cause the pytest
# test case to appropriately fail during the teardown phase to ensure
# that the error is properly surfaced. The ExcHook is intended to be
# used with a pytest autouse fixture. Without the fixture, any
# uncaptured thread failure will appear in the output, but the test case
# itself will not fail. Here's an example autouse fixture with ExcHook.
# .. code-block:: python
#
#    @pytest.fixture(autouse=True)
#    def thread_exc(monkeypatch: Any, request) -> Generator[ExcHook, None, None]:
#        with ExcHook(monkeypatch) as exc_hook:
#            yield exc_hook


# Also, if you need to issue the thread error earlier, before cleanup,
# then specify thread_exc as an argument on the test method and then in
# mainline issue:
#     thread_exc.raise_exc_if_one()
#
# When the above is done, cleanup will not raise the error again.
#
########################################################################
class ExcHook:
    """Context manager exception hook."""

    def __init__(self, monkeypatch) -> None:
        """Initialize the ExcHook class instance."""
        self.exc_err_msg1 = ""
        self.old_hook = None
        self.new_hook = None
        self.mpatch = monkeypatch

    def raise_exc_if_one(self) -> None:
        """Raise an error is we have one.

        Raises:
            Exception: exc_msg

        """
        if self.exc_err_msg1:
            exc_msg = self.exc_err_msg1
            self.exc_err_msg1 = ""
            raise Exception(f"{exc_msg}")

    def __enter__(self) -> None:
        """Context manager enter method."""
        self.old_hook = threading.excepthook  # save to restore in __exit__
        ExcHook.mock_threading_excepthook.exc_hook = self
        # replace the current hook with our ExcHook
        self.mpatch.setattr(threading, "excepthook", ExcHook.mock_threading_excepthook)
        # keep a copy
        self.new_hook = threading.excepthook
        logger.debug(
            f"ExcHook __enter__ new hook was set: {self.old_hook=}, {self.new_hook=}"
        )

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit method.

        Args:
            exc_type: exception type or None
            exc_val: exception value or None
            exc_tb: exception traceback or None

        """
        # surface any remote thread uncaught exceptions
        self.raise_exc_if_one()

        # the following check ensures that the test case waited via join for
        # any started threads to come home
        if threading.active_count() > 1:
            for idx, thread in enumerate(threading.enumerate()):
                logger.debug(f"active thread {idx}: {thread}")
        assert (
            threading.active_count() == 1
        ), f"{threading.active_count()-1} threads failed to complete"

        # the following assert ensures our ExcHook is still active

        assert threading.excepthook == self.new_hook, (
            f"ExcHook {self.new_hook=} was incorrectly replaced at some point by "
            f"{threading.excepthook=}"
        )
        logger.debug(
            f"ExcHook __exit__ current hook {threading.excepthook=} will now be restored "
            f"from {self.old_hook=}"
        )
        threading.excepthook = self.old_hook

    @staticmethod
    def mock_threading_excepthook(args: Any) -> None:
        """Build error message from exception.

        Args:
            args: contains:
                      args.exc_type: Optional[Type[BaseException]]
                      args.exc_value: Optional[BaseException]
                      args.exc_traceback: Optional[TracebackType]

        Raises:
            Exception: Test case thread test error

        """
        exc_err_msg = (
            f"Test case excepthook: {args.exc_type=}, "
            f"{args.exc_value=}, {args.exc_traceback=},"
            f" {args.thread=}"
        )
        traceback.print_tb(args.exc_traceback)
        logger.debug(exc_err_msg)
        current_thread = threading.current_thread()
        logging.exception(f"exception caught for {current_thread}")
        logger.debug(f"excepthook current thread is {current_thread}")
        exc_hook = getattr(ExcHook.mock_threading_excepthook, "exc_hook", None)
        exc_hook.exc_err_msg1 = exc_err_msg
        raise Exception(f"Test case thread test error: {exc_err_msg}")
