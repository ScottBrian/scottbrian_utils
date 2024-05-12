"""Module entry_trace.

===========
entry_trace
===========

The etrace decorator can be used on a function or method to add a
debug log item upon entry and exit. The entry trace log item will
include the filename, function or method name, the line number where it
is defined, and the specified args and/or kwargs. The exit trace will
include the return value.

The decorator can be controlled via the following parameters:

    1) enable_trace: boolean value that when True will enable the trace.
       The default is True.
    2) omit_parms: list of parameter names whose argument values should
       appear in the trace as ellipses. This can help reduce the size
       of the trace entry for large arguments. The default is None.
    3) omit_return_value: if True, do not trace the return value in the
       exit trace entry. The default is False.


:Example 1: Decorate a function with no args nor kwargs.

.. code-block:: python

    from scottbrian_utils.entry_trace import etrace

    @etrace
    def f1() -> None:
        pass

    f1()


Expected trace output for Example 1::

    test_entry_trace.py:f1:69 entry: caller: test_entry_trace.py::TestEntryTraceExamples.test_etrace_example1:77
    test_entry_trace.py:f1:69 exit: return_value=None


:Example 2: Decorate a function that has 1 positional arg and 1 keyword
            arg.

.. code-block:: python

    from scottbrian_utils.entry_trace import etrace

    @etrace
    def f1(a1: int, kw1: str = "42") -> str:
        return f"{a1=}, {kw1=}"

    f1(42, kw1="forty two")


Expected trace output for Example 2::

    test_entry_trace.py:f1:122 entry: a1=42, kw1='forty two', caller: test_entry_trace.py::TestEntryTraceExamples.test_etrace_example2:130
    test_entry_trace.py:f1:122 exit: return_value="a1=42, kw1='forty two'"


:Example 3: Decorate two functions, the first with etrace enabled and
            the second with etrace disabled.

.. code-block:: python

    from scottbrian_utils.entry_trace import etrace

    do_trace: bool = True

    @etrace(enable_trace=do_trace)
    def f1(a1: int, kw1: str = "42") -> str:
        return f"{a1=}, {kw1=}"

    do_trace: bool = False

    @etrace(enable_trace=do_trace)
    def f2(a1: int, kw1: str = "42"):
        return f"{a1=}, {kw1=}"

    f1(42, kw1="forty two")
    f2(24, kw1="twenty four")

Expected trace output for Example 3::

    test_entry_trace.py:f1:180 entry: a1=42, kw1='forty two', caller: test_entry_trace.py::TestEntryTraceExamples.test_etrace_example3:194
    test_entry_trace.py:f1:180 exit: return_value="a1=42, kw1='forty two'"


:Example 4: Decorate a function with the positional arg omitted.

.. code-block:: python

    from scottbrian_utils.entry_trace import etrace

    @etrace(omit_parms=["a1"])
    def f1(a1: int, kw1: str = "42") -> str:
        return f"{a1=}, {kw1=}"

    f1(42, kw1="forty two")

Expected trace output for Example 4::

    test_entry_trace.py:f1:244 entry: a1='...', kw1='forty two', caller: test_entry_trace.py::TestEntryTraceExamples.test_etrace_example4:252
    test_entry_trace.py:f1:244 exit: return_value="a1=42, kw1='forty two'"


:Example 5: Decorate a function with the first keyword arg omitted.

.. code-block:: python

    from scottbrian_utils.entry_trace import etrace

    @etrace(omit_parms="kw1")
    def f1(a1: int, kw1: str = "42", kw2: int = 24) -> str:
        return f"{a1=}, {kw1=}, {kw2=}"

    f1(42, kw1="forty two", kw2=84)

Expected trace output for Example 5::

    test_entry_trace.py:f1:300 entry: a1=42, kw1='...', kw2=84, caller: test_entry_trace.py::TestEntryTraceExamples.test_etrace_example5:308
    test_entry_trace.py:f1:300 exit: return_value="a1=42, kw1='forty two', kw2=84"


:Example 6: Decorate a function with the return value omitted.

.. code-block:: python

    from scottbrian_utils.entry_trace import etrace

    @etrace(omit_return_value=True)
    def f1(a1: int, kw1: str = "42", kw2: int = 24) -> str:
        return f"{a1=}, {kw1=}, {kw2=}"

    f1(42, kw1="forty two", kw2=84)

Expected trace output for Example 6::

    test_entry_trace.py:f1:347 entry: a1=42, kw1='forty two', kw2=84, caller: test_entry_trace.py::TestEntryTraceExamples.test_etrace_example6:356
    test_entry_trace.py:f1:347 exit: return value omitted

  .. # noqa: E501, W505

"""

########################################################################
# Standard Library
########################################################################
from collections.abc import Iterable
import functools
import inspect
import logging
from typing import Any, Callable, cast, Optional, overload, TypeVar, Union

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


@overload
def etrace(
    wrapped: F,
    *,
    enable_trace: Union[bool, Callable[..., bool]] = True,
    omit_parms: Optional[Iterable[str]] = None,
    omit_return_value: bool = False,
    latest: int = 1,
    depth: int = 1,
) -> F:
    pass


@overload
def etrace(
    *,
    enable_trace: Union[bool, Callable[..., bool]] = True,
    omit_parms: Optional[Iterable[str]] = None,
    omit_return_value: bool = False,
    latest: int = 1,
    depth: int = 1,
) -> Callable[[F], F]:
    pass


def etrace(
    wrapped: Optional[F] = None,
    *,
    enable_trace: Union[bool, Callable[..., bool]] = True,
    omit_parms: Optional[Iterable[str]] = None,
    omit_return_value: bool = False,
    latest: int = 1,
    depth: int = 1,
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
        latest: specifies the position in the call sequence that is to
            be designated as the caller named in the trace output. A
            value of 1, the default, specifies that the caller is one
            call back in the sequence and is the normal case. A value
            greater than 1 is useful when decorators are stacked and the
            caller of interest is thus further back in the sequence.
        depth: specifies the depth of the call sequence to include in
            the trace output. A value of 1, the default, species that
            only the latest caller is to be included. Values greater
            than 1 will include the latest caller and its callers.

    Returns:
        funtools partial (when wrapped is None) or decorated function

    Notes:

        1) In both the entry and exit trace, the line number following
           the decorated function or method will be the line number of
           the etrace decorator. The trace message itself, however, will
           include the name of the traced function or method along with
           the line number where it is defined.
        2) The positional and keyword arguments (if any) will appear
           after "entry:".
        3) The caller of the traced function or method will appear after
           "caller:" and will include the line number of the call.
        4) The exit trace will include the return value unless
           *omit_return_value* specifies True.

    """
    if wrapped is None:
        return cast(
            F,
            functools.partial(
                etrace,
                enable_trace=enable_trace,
                omit_parms=omit_parms,
                omit_return_value=omit_return_value,
                latest=latest,
                depth=depth,
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

    target = f"{target_file}::{target_name}:{target_line_num}"

    if type(wrapped).__name__ == "classmethod":
        target_sig = inspect.signature(wrapped.__func__)  # type: ignore
        skip_self_cls = True
    else:
        target_sig = inspect.signature(wrapped)

    target_sig_array: dict[str, Any] = {}
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
    def trace_wrapper(
        wrapped: F,
        instance: Optional[Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
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
            f"{get_formatted_call_sequence(latest=latest, depth=depth)}"
        )

        return_value = wrapped(*args, **kwargs)

        if omit_return_value:
            logger.debug(f"{target} exit: return value omitted")
        else:
            logger.debug(f"{target} exit: {return_value=}")
        return return_value

    return cast(F, trace_wrapper(wrapped))
