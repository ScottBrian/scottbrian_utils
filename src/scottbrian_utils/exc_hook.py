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
from typing import Any, Callable, Optional
import logging

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence

########################################################################
# setup the logger
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
#    def thread_exc(monkeypatch: Any, request
#                  ) -> Generator[ExcHook, None, None]:
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

    ####################################################################
    # __init__
    ####################################################################
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Initialize the ExcHook class instance."""
        self.exc_err_type: Optional[type[Exception]] = None
        self.exc_err_msg: str = ""
        self.old_hook: Callable[[threading.ExceptHookArgs], Any]
        self.new_hook: Callable[[threading.ExceptHookArgs], Any]
        self.mpatch: pytest.MonkeyPatch = monkeypatch

    ####################################################################
    # raise_exc_if_one
    ####################################################################
    def raise_exc_if_one(self) -> None:
        """Raise an error if we have one.

        Raises:
            Exception: exc_msg

        """
        if self.exc_err_type is not None:
            exception = self.exc_err_type
            self.exc_err_type = None
            logger.debug(
                f"caller {get_formatted_call_sequence(latest=1, depth=1)} is raising "
                f'Exception: "{self.exc_err_msg}"'
            )

            raise exception(f"{self.exc_err_msg}")

    ####################################################################
    # __enter__
    ####################################################################
    def __enter__(self) -> "ExcHook":
        """Context manager enter method."""
        self.old_hook = threading.excepthook  # save to restore in __exit__

        # replace the current hook with our ExcHook
        self.mpatch.setattr(threading, "excepthook", ExcHook.mock_threading_excepthook)
        # keep a copy
        self.new_hook = threading.excepthook

        logger.debug(
            f"ExcHook __enter__ new hook was set: {self.old_hook=}, "
            f"{self.new_hook=}"
        )
        return self

    ####################################################################
    # __exit__
    ####################################################################
    def __exit__(self, exc_type: type[Exception], exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit method.

        Args:
            exc_type: exception type or None
            exc_val: exception value or None
            exc_tb: exception traceback or None

        """
        ################################################################
        # restore the original hook
        ################################################################
        replaced_hook = threading.excepthook
        threading.excepthook = self.old_hook
        logger.debug(
            "ExcHook __exit__ hook in threading.excepthook restored, "
            f"changed from {replaced_hook} to {self.old_hook=}"
        )

        # the following code ensures our ExcHook was still in place
        # before we restored it
        if replaced_hook != self.new_hook:
            raise RuntimeError(
                f"ExcHook {self.new_hook=} was incorrectly replaced at some point by "
                f"{replaced_hook}"
            )

        # the following check ensures that the test case waited via join
        # for any started threads to complete
        if threading.active_count() > 1:
            singular_plural_str = "s" if threading.active_count() > 2 else ""
            logger.debug(
                f"{threading.active_count() - 1} thread{singular_plural_str} failed to complete"
            )
            for idx, thread in enumerate(threading.enumerate()):
                logger.debug(f"active thread {idx}: {thread}")
            raise RuntimeError(
                f"{threading.active_count() - 1} thread{singular_plural_str} failed to complete"
            )

        # surface any remote thread uncaught exceptions
        self.raise_exc_if_one()

    ####################################################################
    # mock_threading_excepthook
    ####################################################################
    @staticmethod
    def mock_threading_excepthook(args: Any) -> None:
        """Build and save error message from exception.

        Args:
            args: contains:
                      args.exc_type: Optional[Type[BaseException]]
                      args.exc_value: Optional[BaseException]
                      args.exc_traceback: Optional[TracebackType]

        """
        # The error message is built and saved in the exc_hook instance
        # and will be issued with an exception when __exit__ or the
        # test case calls raise_exc_if_one
        exc_hook = getattr(ExcHook.mock_threading_excepthook, "exc_hook")

        traceback.print_tb(args.exc_traceback)

        exc_hook.exc_err_type = args.exc_type
        exc_hook.exc_err_msg = (
            f"Test case excepthook: {args.exc_type=}, "
            f"{args.exc_value=}, {args.exc_traceback=},"
            f" {args.thread=}"
        )
