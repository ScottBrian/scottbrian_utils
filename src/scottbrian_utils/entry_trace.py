"""Module entry_trace.

===========
entry_trace
===========

The etrace decorator can be used on a function or method to add a
debug log item upon entry and exit. The entry trace log item will
include the filename, function or method name, the line number where it
is defined, and the specified args and/or kwargs. The exit trace will
include the return value.

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

    entry_trace.py: trace_wrapper: 145 entry_trace.py:f1:44 entry:
        args=(), kwargs=(), caller: entry_trace.py:48
    entry_trace.py: trace_wrapper: 152 entry_trace.py:f1:44 exit:
        ret_value=None


"""

########################################################################
# Standard Library
########################################################################
from collections.abc import Iterable
import functools
import inspect
import logging
from typing import Any, Callable, cast, Never, Optional, TypeVar, Union

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
        funtools partial (when wrapped is None) or decorated function

    Notes:

        1) In both the entry and exit trace, the line number following
           the decorated function or method will be the line number of
           the etrace decorator.

    """
    if wrapped is None:
        return cast(
            F,
            functools.partial(
                etrace,
                enable_trace=enable_trace,
                omit_parms=omit_parms,
                omit_return_value=omit_return_value,
            ),
        )

    omit_parms = set({omit_parms} if isinstance(omit_parms, str) else omit_parms or "")

    if type(wrapped).__name__ in ("staticmethod", "classmethod"):
        target_file = inspect.getsourcefile(wrapped.__wrapped__).split(  # type: ignore
            "\\"
        )[-1]
    else:
        target_file = inspect.getsourcefile(wrapped).split("\\")[-1]  # type: ignore

    qual_name_list = wrapped.__qualname__.split(".")

    skip_self_cls = False
    if len(qual_name_list) == 1 or qual_name_list[-2] == "<locals>":
        # set target_name to function name
        target_name = qual_name_list[-1]
    else:
        # set target_name to class name and method name
        target_name = f":{qual_name_list[-2]}.{qual_name_list[-1]}"
        if type(wrapped).__name__ != "staticmethod":
            skip_self_cls = True

    try:
        target_line_num: Union[int, str] = inspect.getsourcelines(wrapped)[1]
    except OSError:
        target_line_num = "?"

    target = f"{target_file}:{target_name}:{target_line_num}"

    if type(wrapped).__name__ == "classmethod":
        target_sig = inspect.signature(wrapped.__func__)  # type: ignore
        skip_self_cls = True
    else:
        target_sig = inspect.signature(wrapped)

    target_sig_array = {}
    target_sig_names = []
    target_sig_kind = []
    var_pos_idx = -1

    for pidx, parm in enumerate(target_sig.parameters):
        if pidx == 0 and skip_self_cls:
            continue

        # VAR_KORD (e.g., **kwargs) is not needed in the
        # target_sig_array - there are no defaults for kwargs, and the
        # code below in trace_wrapper will simply add instead of
        # updating the target_sig_array as it encounters any kwargs
        if target_sig.parameters[parm].kind == inspect.Parameter.VAR_KEYWORD:
            continue

        parm_name = target_sig.parameters[parm].name

        def_val = target_sig.parameters[parm].default

        if def_val is inspect.Parameter.empty:
            target_sig_array[parm_name] = "?"
        else:
            target_sig_array[parm_name] = def_val
        target_sig_names.append(parm_name)
        target_sig_kind.append(target_sig.parameters[parm].kind)
        if target_sig.parameters[parm].kind == inspect.Parameter.VAR_POSITIONAL:
            var_pos_idx = len(target_sig_kind) - 1

    @wrapt.decorator(enabled=enable_trace)  # type: ignore
    def trace_wrapper(wrapped: F, instance: Any, args: Any, kwargs: Any) -> Any:
        """Setup the trace."""
        log_sig_array = ""
        target_sig_array_copy = target_sig_array.copy()

        # for VAR_POSITIONAL, we can have a signature of f(*args), or
        # we can have, for example, f(a1, *args). So, we keep track of
        # the index of the *args keyword and use it here to load the
        # trace values appropriately. Note that we can't have
        # f(*args, a1), so once we determine we are now at a
        # VAR_POSITIONAL index we simply load the remainder of the
        # positional args into a tuple and place that into the array,
        # and then break out of the loop.

        for idx, arg in enumerate(args):
            if target_sig_kind[idx] == inspect.Parameter.VAR_POSITIONAL:
                target_sig_array_copy[target_sig_names[idx]] = tuple(args[idx:])
                break
            target_sig_array_copy[target_sig_names[idx]] = arg

        for key, item in kwargs.items():
            target_sig_array_copy[key] = item

        for omit_parm_name in omit_parms:
            if omit_parm_name in target_sig_array_copy:
                target_sig_array_copy[omit_parm_name] = "..."
            else:
                raise ValueError(
                    f"{omit_parm_name} specified in omit_parms is not a known parameter"
                )

        if (
            var_pos_idx >= 0
            and target_sig_array_copy[target_sig_names[var_pos_idx]] == "?"
        ):
            del target_sig_array_copy[target_sig_names[var_pos_idx]]

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
