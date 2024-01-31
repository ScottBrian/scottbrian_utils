"""Module entry_trace.

===========
entry_trace
===========

The etrace decorator can be used on a function or method to add a
debug log item upon entry and exit. The log item will include the
filename, function or method name, and the line number where it is
defined. The entry trace will include the specified args and kwargs and
the caller filename, function or method name, and the line number where
it is defined. The exit trace will include the return value.

The decorator can be statically enabled or disabled via a set of
parameters as follows:

    1) enable_trace: boolean value that when True will enable the trace
       unless the function or method name is specified in the
       exclude_list (see below). If False, the trace will be
       disabled unless the function or method name is specified in the
       include_list (see below). The default is True.
    2) exclude_list: list of string values that name functions or
       methods that should not be traced when enable_trace is True. The
       default is None.
    3) include_list: list of string values that name functions or
       methods that should be traced when enable_trace is False or when
       the name is also specified in the exclude_list. The default is
       None.
    4) trace_args: boolean value that when True will cause the function
       or method input args to be traced. When False, no args will be
       traced. The default is True.
    5) omit_kwargs: list of string values that are names of kwargs that
       should not be traced. The default is None.
    6) extra_args: list off string values that are names of variables
       that should be included in the trace. The default is None.


:Example 1: Decorate a function that has no args and no kwargs.

.. code-block:: python

    from scottbrian_utils.entry_trace import etrace

    @etrace
    def f1() -> None:
        pass

    f1()


Expected trace output for Example 1::

    entry_trace.py: trace_wrapper: 145 entry_trace.py:f1:44 entry: args=(), kwargs=(),
        caller: entry_trace.py:48
    entry_trace.py: trace_wrapper: 152 entry_trace.py:f1:44 exit: ret_value=None


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
# etrace decorator
####################################################################
def etrace(
    wrapped=None,
    *,
    enable_trace: bool = True,
    exclude_list: Optional[list[str]] = None,
    include_list: Optional[list[str]] = None,
    trace_args: bool = True,
    omit_kwargs: Optional[Iterable[str]] = None,
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
            etrace,
            enable_trace=enable_trace,
            exclude_list=exclude_list,
            include_list=include_list,
            trace_args=trace_args,
            omit_kwargs=omit_kwargs,
            extra_args=extra_args,
        )

    omit_kwargs = set(
        {omit_kwargs} if isinstance(omit_kwargs, str) else omit_kwargs or ""
    )
    extra_args = set({extra_args} if isinstance(extra_args, str) else extra_args or "")

    if enable_trace and exclude_list is not None and wrapped.__name__ in exclude_list:
        enable_trace = False
    if (
        not enable_trace
        and include_list is not None
        and wrapped.__name__ in include_list
    ):
        enable_trace = True

    target_file = inspect.getsourcefile(wrapped).split("\\")[-1]
    target_name = wrapped.__name__
    target_line_num = inspect.getsourcelines(wrapped)[1]

    target = f"{target_file}:{target_name}:{target_line_num}"

    @wrapt.decorator(enabled=enable_trace)
    def trace_wrapper(wrapped, instance, args, kwargs):
        """Setup the trace."""
        if trace_args:
            log_args: str = args
        else:
            log_args = ""

        log_kwargs: str = ""
        comma: str = ""
        for key, item in kwargs.items():
            if key not in omit_kwargs and item is not None:
                quote = ""
                if isinstance(item, str):
                    quote = "'"
                log_kwargs = f"{log_kwargs}{comma}{key}={quote}{str(item)}{quote}"
                comma = ", "

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
            f"{target} entry: args={log_args}, kwargs=({log_kwargs}), caller: "
            f"{mod_name}:{func_name}:{line_num}"
        )

        ret_value = wrapped(*args, **kwargs)

        logger.debug(f"{target} exit: {ret_value=}")

        return ret_value

    return trace_wrapper(wrapped)
