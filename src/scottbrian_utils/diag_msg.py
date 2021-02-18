"""diag_msg.py module.

========
diag_msg
========

With **diag_msg** you can print messages with the time and caller info added
automatically. The default time format is H:M:S.f. The caller info includes
the module name, class name (or null), method name (or null), and the line
number relative to the start of the module.

:Example: print a diagnostic message

>>> from scottbrian_utils.diag_msg import diag_msg
>>> diag_msg('this is a diagnostic message')
16:20:05.909260 <input>:1 this is a diagnostic message

Note that all of the examples are done as if entered in a python session from
the console. As such, the module name will show as <input>. When coded in a
module, however, you will see the module name instead of <input>.

"""
from datetime import datetime
from os import fspath
from pathlib import Path
# noinspection PyProtectedMember
from sys import _getframe
from types import FrameType
from typing import Any, NamedTuple

# diag_msg_datetime_fmt = "%b %d %H:%M:%S.%f"
diag_msg_datetime_fmt = "%H:%M:%S.%f"
diag_msg_caller_depth = 1
get_formatted_call_seq_depth = 3


class CallerInfo(NamedTuple):
    """NamedTuple for the caller info used in diag_msg."""
    mod_name: str
    cls_name: str
    func_name: str
    line_num: int


###############################################################################
# diag_msg
###############################################################################
def diag_msg(*args: Any,
             depth: int = diag_msg_caller_depth,
             dt_format: str = diag_msg_datetime_fmt,
             **kwargs: Any) -> None:
    """Print diagnostic message.

    Args:
        args: the text to print as part of the diagnostic message
        depth:  specifies how many callers to include in the call sequence
        dt_format: datetime format to use
        kwargs: keyword args to pass along to the print statement

    :Example: print a diagnostic message from a method with a seq depth of 2

    >>> from scottbrian_utils.diag_msg import diag_msg
    >>> class Cls1:
    ...     @classmethod
    ...     def f1(cls, x):
    ...         # limit to two calls
    ...         diag_msg('diagnostic info', x, depth=2)
    >>> Cls1.f1(42)
    16:20:05.909260 <input>:1 -> <input>::Cls1.f1:5 diagnostic info 42

    :Example: print a diagnostic message with different datetime format

    >>> from scottbrian_utils.diag_msg import diag_msg
    >>> class Cls1:
    ...     def f1(self, x):
    ...         # use different datetime format
    ...         diag_msg('diagnostic info', x, dt_format='%a %b-%d %H:%M:%S')
    >>> Cls1().f1(24)
    Tue Feb-16 10:38:32 <input>::Cls1.f1:4 diagnostic info 24

    """
    # we specify 2 frames back since we don't want our call in the sequence
    caller_sequence = get_formatted_call_sequence(1, depth)

    str_time = datetime.now().strftime(dt_format)

    print(f'{str_time} {caller_sequence}', *args, **kwargs)


###############################################################################
# get_caller_info
###############################################################################
def get_caller_info(frame: FrameType) -> CallerInfo:
    """Return caller information from the given stack frame.

    Args:
        frame: the frame from which to extract caller info

    Returns:
        The caller module name, class name (or null), function name (or null),
        and the line number within the module source

    :Example: get caller info for current frame

    >>> from scottbrian_utils.diag_msg import get_caller_info
    >>> import inspect
    >>> def f1():
    ...     frame = inspect.currentframe()
    ...     return get_caller_info(frame)
    >>> f1()
    CallerInfo(mod_name='<input>', cls_name='', func_name='f1', line_num=3)

    """
    code = frame.f_code
    mod_name = fspath(Path(code.co_filename).name)
    cls_name = ''
    func_name = code.co_name

    if func_name == '<module>':  # if we are a script
        func_name = ''  # no func_name, no cls_name
    else:
        for obj_name, obj in frame.f_globals.items():
            # first try for normal method in class
            try:
                if obj.__dict__[func_name].__code__ is code:
                    cls_name = obj_name
                    break
            except (AttributeError, KeyError):
                pass

            # second try for static or class method
            try:
                if obj.__dict__[func_name].__func__.__code__ is code:
                    cls_name = obj_name
                    break
            except (AttributeError, KeyError):
                pass

    return CallerInfo(mod_name, cls_name, func_name, frame.f_lineno)


###############################################################################
# get_formatted_call_sequence
###############################################################################
def get_formatted_call_sequence(latest: int = 0,
                                depth: int = get_formatted_call_seq_depth
                                ) -> str:
    """Return a formatted string showing the callers.

    Args:
        latest: specifies the stack position of the most recent caller to be
                  included in the call sequence
        depth: specifies how many callers to include in the call sequence

    Returns:
        Formatted string showing for each caller the module name, possibly
        a function name or a class name/method_name pair, and the
        source code line number. There are three basic scenarios:

        * A call from a script will appear as: mod_name:lineno
        * A call from a function will appear as: mod_name::func_name:lineno
        * A call from a class method: mod_name::cls_name.func_name:lineno

    This function is useful if, for example, you want to include the call
    sequence in a log.

    :Example: get call sequence for three callers

    >>> from scottbrian_utils.diag_msg import get_formatted_call_sequence
    >>> def f1():
    ...     # f1 now on stack
    ...     # call f2
    ...     f2()
    >>> def f2():
    ...     # call f3
    ...     f3()
    >>> def f3():
    ...     # f3 now latest entry in call sequence
    ...     # default is to get three most recent calls
    ...     print(get_formatted_call_sequence())
    >>> f1()
    <input>::f1:4 -> <input>::f2:3 -> <input>::f3:4

    Note that when coded in a module, you will get the module name in the
    sequence instead of <input>, and the line numbers will be relative from
    the start of the module instead of from each of the function definition
    sections.

    :Example: get call sequence for last two callers

    >>> from scottbrian_utils.diag_msg import get_formatted_call_sequence
    >>> def f1():
    ...     # f1 now on stack
    ...     # call f2
    ...     f2()
    >>> def f2():
    ...     # call f3
    ...     f3()
    >>> def f3():
    ...     # f3 now latest entry in call sequence
    ...     # specify depth to get two most recent calls
    ...     call_seq = get_formatted_call_sequence(depth=2)
    ...     print(call_seq)
    >>> f1()
    <input>::f2:3 -> <input>::f3:4

    :Example: get call sequence for two callers, one caller back

    >>> from scottbrian_utils.diag_msg import get_formatted_call_sequence
    >>> def f1():
    ...     # f1 now on stack
    ...     # call f2
    ...     f2()
    >>> def f2():
    ...     # call f3
    ...     f3()
    >>> def f3():
    ...     # f3 now latest entry in call sequence
    ...     # specify latest to go back 1 and thus ignore f3
    ...     # specify depth to get two calls from latest going back
    ...     call_seq = get_formatted_call_sequence(latest=1, depth=2)
    ...     print(call_seq)
    >>> f1()
    <input>::f1:4 -> <input>::f2:3

    :Example: get sequence for script call to class method

    >>> from scottbrian_utils.diag_msg import get_formatted_call_sequence
    >>> class Cls1:
    ...     def f1(self):
    ...         # limit to two calls
    ...         call_seq = get_formatted_call_sequence(depth=2)
    ...         print(call_seq)
    >>> a_cls1 = Cls1()
    >>> a_cls1.f1()
    <input>:1 -> <input>::Cls1.f1:4

    """
    caller_sequence = ''  # init to null
    arrow = ''  # start with no arrow for first iteration
    for caller_depth in range(latest+1, latest+1+depth):
        try:
            # sys._getframe is faster than inspect.currentframe
            frame = _getframe(caller_depth)
        except ValueError:
            break  # caller_depth beyond depth of frames

        try:
            # mod_name, cls_name, func_name, lineno = get_caller_info(frame)
            caller_info = get_caller_info(frame)
        finally:
            del frame  # important to prevent storage leak

        dot = '.' if caller_info.cls_name else ''
        colon = '::' if caller_info.func_name else ''

        caller_sequence = f'{caller_info.mod_name}{colon}' \
                          f'{caller_info.cls_name}{dot}' \
                          f'{caller_info.func_name}:'\
                          f'{caller_info.line_num}{arrow}' \
                          f'{caller_sequence}'
        arrow = ' -> '  # set arrow for subsequent iterations

    return caller_sequence
