"""Module entry_trace.

===========
entry_trace
===========

The fun_trace decorator can be used on a function or method to add a
debug log item upon entry and exit. The log item will include the
caller's name and line number along with the passed aruments.

:Example: create a timer and use in a loop

>>> from scottbrian_utils.entry_trace import fun_trace
>>> import time
>>> def example1(parm1: int, parm2: str, parm3: list[str]) -> str:
...     print('example1 entered')
...     timer = Timer(timeout=3)
...     for idx in range(10):
...         print(f'idx = {idx}')
...         time.sleep(1)
...         if timer.is_expired():
...             print('timer has expired')
...             break
...     print('example1 exiting')
>>> example1()
example1 entered
idx = 0
idx = 1
idx = 2
timer has expired
example1 exiting


The timer module contains:

    1) Timer class with methods:

       a. is_expired

"""
########################################################################
# Standard Library
########################################################################
from collections.abc import Iterable
import functools
import inspect
import logging
from os import fspath
from pathlib import Path
import sys
from typing import Optional

########################################################################
# Third Party
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence, get_caller_info
import wrapt

logger = logging.getLogger(__name__)


####################################################################
# fun_trace decorator
####################################################################
def fun_trace(
    wrapped=None,
    *,
    logger_is_enabled: bool = True,
    log_msg_prefix: str = "",
    exclude_list: Optional[list[str]] = None,
    include_list: Optional[list[str]] = None,
    omit_args: Optional[Iterable[str]] = None,
    extra_args: Optional[Iterable[str]] = None,
):
    """Decorator to produce entry/exit log.

    Args:
        wrapped: function to be decorated

    Returns:
        decorated function

    """
    if wrapped is None:
        return functools.partial(
            fun_trace,
            logger_is_enabled=logger_is_enabled,
            log_msg_prefix=log_msg_prefix,
            exclude_list=exclude_list,
            include_list=include_list,
            omit_args=omit_args,
            extra_args=extra_args,
        )

    if log_msg_prefix:
        log_msg_prefix = f"{log_msg_prefix} "  # add space
    omit_args = set({omit_args} if isinstance(omit_args, str) else omit_args or "")
    extra_args = set({extra_args} if isinstance(extra_args, str) else extra_args or "")

    if (
        logger_is_enabled
        and exclude_list is not None
        and wrapped.__name__ in exclude_list
    ):
        logger_is_enabled = False
    if (
        not logger_is_enabled
        and include_list is not None
        and wrapped.__name__ in include_list
    ):
        logger_is_enabled = True

    target_file = inspect.getsourcefile(wrapped).split("\\")[-1]
    target_name = wrapped.__name__
    target_line_num = inspect.getsourcelines(wrapped)[1]

    target = f"{target_file}:{target_name}:{target_line_num}"

    @wrapt.decorator(enabled=logger_is_enabled)
    def trace_wrapper(wrapped, instance, args, kwargs):
        """Setup the trace."""
        log_args: str = ""
        log_kwargs: str = ""
        comma: str = ""
        for key, item in kwargs.items():
            if key not in omit_args and item is not None:
                log_kwargs = f"{log_kwargs}{comma} {key}={item}"
                comma = ","

        for extra_arg in extra_args:
            log_args = f"{log_args}{comma} {extra_arg}={eval(extra_arg)}"
            comma = ","

        # prefix = (
        #     f"{target}"
        #     f"{get_formatted_call_sequence(latest=1, depth=1)}->"
        #     f"{wrapped.__name__}:{target_line_num}"
        # )
        # entry_log_msg = f"{prefix} entry:{log_args}"
        # exit_log_msg = f"{prefix} exit:{log_args}"
        frame = sys._getframe(1)
        code = frame.f_code
        mod_name = fspath(Path(code.co_filename).name)
        func_name = code.co_name
        line_num = frame.f_lineno
        del frame
        # caller_info = get_caller_info(frame: FrameType)

        # logger.debug(
        #     f"{target} entry:{log_args}, caller: "
        #     f"{get_formatted_call_sequence(latest=1, depth=1)}"
        # )
        logger.debug(
            f"{target} entry: args=({log_args}), kwargs=({log_kwargs}), caller: "
            f"{mod_name}:{func_name}:{line_num}"
        )

        ret_value = wrapped(*args, **kwargs)

        logger.debug(f"{target} exit: {ret_value=}")

        return ret_value

    return trace_wrapper(wrapped)
