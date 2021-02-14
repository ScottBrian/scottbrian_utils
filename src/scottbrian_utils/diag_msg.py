"""diag_msg.py module.

========
diag_msg
========

With **diag_msg** you can print messages with the time and caller info as a
diagnotic aid like this:

:Example: print a diagnostic message

>>> from scottbrian_utils.diag_msg import diag_msg
>>> diag_msg('This is my diagnostic message')
<BLANKLINE>
01/21/2020 18:27:33.123456 diag_msg.py:13 This is my diagnostic message


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
diag_msg_caller_depth = 3
get_formatted_call_seq_depth = 3


class CallerInfo(NamedTuple):
    """Structure for the caller info used in diag_msg."""
    mod_name: str
    cls_name: str
    func_name: str
    line_num: int


# def get_caller_info(frame: FrameType) -> Tuple[str, str, str, int]:
def get_caller_info(frame: FrameType) -> CallerInfo:
    """Return caller information from the given stack frame.

    Args:
        frame: the frame from which to extract caller info

    Returns:
        The caller module name, class name (or null), function name (or null),
        and the line number within the module source

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
            # try:
            #     assert obj.__dict__[func_name].__code__ is code
            # except (AssertionError, KeyError):
            #     pass
            # else:  # obj is the class that defines our method
            #     cls_name = obj_name
            #     break
            #
            # # second try is for static or class method
            # try:
            #     assert obj.__dict__[func_name].__func__.__code__ is code
            # except (AssertionError, KeyError):
            #     pass
            # else:
            #     cls_name = obj_name
            #     break

    return CallerInfo(mod_name, cls_name, func_name, frame.f_lineno)


def get_formatted_call_sequence(latest: int = 0,
                                depth: int = get_formatted_call_seq_depth
                                ) -> str:
    """Return a formatted string showing the callers.

    Args:
        latest: specifies the stack position of the most recent caller to be
                  included in the call sequence
        depth: specifies how many callers to include in the call sequence

    Returns:
          Formatted string showing for each caller the module name and
            possibly a function name or a class name/method_name pair, and the
            source code line number. There are a few different scenarios that
            will result in how the information is presented:
            1) the call came from the module running as a script:
               module_name:lineno
            2) the call came from a function defined in the module
               module_name::function_name:lineno
            3) the call came from a method in a class defined in the module
               module_name::class_name.method_name:lineno
            Multiply calls in the sequence will be delimited with the string:
              ' -> '
              For example:
              mod1::fun1:123 -> mod1::fun2:145 -> mod2::class1.method1:234
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

    """
    # we specify 2 frames back since we don't want our call in the sequence
    caller_sequence = get_formatted_call_sequence(1, depth)

    str_time = datetime.now().strftime(dt_format)

    print(f'{str_time} {caller_sequence}', *args, **kwargs)

def tell_me(file_arg):
    if file_arg == sys.stdout:
        print('std out is the arg')

    if file_arg == sys.stderr:
        print('std err is the arg')

    if file_arg.name == '<stderr>':
        print('name is std err')

    if file_arg.name == '<stdout>':
        print('name is std out')

if __name__ == '__main__':
    import sys
    text = ['three', 'items', 'for you']
    dt_format = '%H:%M:%S.%f'
    depth = 2
    file_arg = 'sys.stderr'
    # print('file_arg:')
    # print(file_arg.name)
    # DiagMsgArgs(arg_bits=7, dt_format_arg='%H:%M', depth_arg=2,
    #             msg_arg=['three', 'items', 'for you'], file_arg='sys.stdout')
    diag_msg(*text, depth=2, file=eval(file_arg))

    if eval(file_arg) == sys.stdout:
        print('std out is the arg')

    if eval(file_arg) == sys.stderr:
        print('std err is the arg')

    # if file_arg.name == '<stderr>':
    #     print('name is std err')
    #
    # if file_arg.name == '<stdout>':
    #     print('name is std out')

    # tell_me(file_arg)
