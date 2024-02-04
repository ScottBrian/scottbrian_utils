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

    1) enable_trace: boolean value that when True will enable the trace.
       The default is True.
    2) omit_parms: list of parameter names whose argument values should
       appear in the trace as ellipses. This can help reduce the size
       of the trace entry for large arguments. The default is None.
    4) omit_return_value: if True, do not trace the return value in the
       exit trace entry. The default is False.


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
from typing import Any, Callable, cast, Optional, TypeVar, Union

########################################################################
# Third Party
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence
import wrapt

logger = logging.getLogger(__name__)


####################################################################
# etrace decorator
####################################################################
F = TypeVar("F", bound=Callable[..., Any])


def etrace(
    wrapped: Optional[F] = None,
    *,
    enable_trace: Union[bool, Callable[..., bool]] = True,
    omit_parms: Optional[Iterable[str]] = None,
    omit_return_value: bool = False,
) -> F:
    """Decorator to produce entry/exit log.

    Args:
        wrapped: function to be decorated
        enable_trace: if True, trace the entry and exit for the
            decorated function or method.
        omit_parms: list of parameter names whose argument values should
            appear in the trace as ellipses. This can help reduce the
            size of the trace entry for large arguments.
        omit_return_value: if True, do not place the return value into
            the exit trace entry.

    Returns:
        decorated function

    Notes:

        1) In both the entry and exit trace, the line number following
           the decorated function or method will be the line number of
           the etrace decorator.

    """
    print(f"entered etrace")
    if wrapped is None:
        return functools.partial(
            etrace,
            enable_trace=enable_trace,
            omit_parms=omit_parms,
            omit_return_value=omit_return_value,
        )

    omit_parms = set({omit_parms} if isinstance(omit_parms, str) else omit_parms or "")

    if type(wrapped).__name__ in ("staticmethod", "classmethod"):
        target_file = inspect.getsourcefile(wrapped.__wrapped__).split("\\")[-1]
    else:
        target_file = inspect.getsourcefile(wrapped).split("\\")[-1]

    qual_name_list = wrapped.__qualname__.split(".")

    if len(qual_name_list) == 1 or qual_name_list[-2] == "<locals>":
        # set target_name to function name
        target_name = qual_name_list[-1]
    else:
        # set target_name to class name and method name
        target_name = f":{qual_name_list[-2]}.{qual_name_list[-1]}"

    try:
        target_line_num = inspect.getsourcelines(wrapped)[1]
    except OSError:
        target_line_num = "444"

    target = f"{target_file}:{target_name}:{target_line_num}"

    if type(wrapped).__name__ == "classmethod":
        target_sig = inspect.signature(wrapped.__func__)
    else:
        target_sig = inspect.signature(wrapped)

    target_sig_array = {}
    target_sig_names = []
    for parm in target_sig.parameters:
        parm_name = target_sig.parameters[parm].name
        def_val = target_sig.parameters[parm].default
        # if def_val is inspect._empty:
        if def_val is inspect.Parameter.empty:
            target_sig_array[parm_name] = "?"
        else:
            target_sig_array[parm_name] = def_val
        target_sig_names.append(parm_name)

    @wrapt.decorator(enabled=enable_trace)
    def trace_wrapper(wrapped, instance, args, kwargs):
        """Setup the trace."""
        log_sig_array = ""
        target_sig_array_copy = target_sig_array.copy()

        for idx, arg in enumerate(args):
            target_sig_array_copy[target_sig_names[idx]] = arg

        for key, item in kwargs.items():
            target_sig_array_copy[key] = item

        for key in omit_parms:
            target_sig_array_copy[key] = "..."

        for key, item in target_sig_array_copy.items():
            if isinstance(item, str) and item != "?":
                log_sig_array = f"{log_sig_array}{key}='{item}', "
            else:
                log_sig_array = f"{log_sig_array}{key}={item}, "

        logger.debug(
            f"{target} entry: {log_sig_array}caller: "
            f"{get_formatted_call_sequence(latest=1, depth=1)}"
        )

        return_value = wrapped(*args, **kwargs)

        if omit_return_value:
            logger.debug(f"{target} exit: return value omitted")
        else:
            logger.debug(f"{target} exit: {return_value=}")
        return return_value

    return cast(F, trace_wrapper(wrapped))
