"""Module time_hdr.

========
time_hdr
========

With **@time_box**, you can decorate a function to be sandwiched between start
time and end time messages like this:

:Example: decorate a function with time_box

>>> from scottbrian_utils.time_hdr import time_box

>>> @time_box
... def func2() -> None:
...      print('2 * 3 =', 2*3)

>>> func2()
<BLANKLINE>
**********************************************
* Starting func2 on Mon Jun 29 2020 18:22:50 *
**********************************************
2 * 3 = 6
<BLANKLINE>
********************************************
* Ending func2 on Mon Jun 29 2020 18:22:51 *
* Elapsed time: 0:00:00.001204             *
********************************************


The time_hdr module contains two items:

    1) StartStopHeader class with two functions that will repectively print
       a starting time and ending time messages in a flower box (see
       flower_box module in scottbrian_utils package).
    2) a time_box decorator that wraps a function and uses the StartStopHeader
       to print the starting and ending time messages.

time_box imports functools, sys, datetime, wrapt, and types from typing

"""

import functools
from datetime import datetime
from typing import Any, Callable, cast, Dict, NewType, Optional, \
    Tuple, TypeVar, Union

from typing import overload

from wrapt.decorators import decorator  # type: ignore

from scottbrian_utils.flower_box import print_flower_box_msg


DT_Format = NewType('DT_Format', str)


class StartStopHeader:
    """Supports the time_box decorator.

     Provides:

        1) a place to store the start time and end time
        2) method print_start_msg to print the start header with the start time
        3) method print_end_msg to print the end trailer with end time and
           elapsed time

    While there might be some standalone uses for this class and its methods,
    its intended use is by the time_box decorator described later in this
    module.
    """
    default_dt_format: DT_Format = DT_Format('%a %b %d %Y %H:%M:%S')

    def __init__(self, func_name: str) -> None:
        """Store the input func_name and set the start and end times to None.

        Args:
            func_name: The name of the function to appear in the start and
                         stop messages
        """
        self.func_name = func_name
        self.start_DT: datetime = datetime.max
        self.end_DT: datetime = datetime.min

    def print_end_msg(self, dt_format: DT_Format = default_dt_format,
                      **kwargs: Any) -> None:
        """Issue end time message in a flower box.

        The end message includes the current datetime and elapsed time
        (calculated as the difference between the end time and the saved start
        time - see the *print_start_msg* method).

        Args:
            dt_format: Specifies the datetime format to use in the end time
                         message. The default is
                         StartStopHeader.default_dt_format.
            kwargs: Specifies the print arguments to use on the print
                      statement, such as *end*, *file*, or *flush*.
        """
        self.end_DT = datetime.now()
        msg1 = 'Ending ' + self.func_name + ' on ' \
               + self.end_DT.strftime(dt_format)
        msg2 = 'Elapsed time: ' + str(self.end_DT - self.start_DT)
        print_flower_box_msg([msg1, msg2], **kwargs)

    def print_start_msg(self, dt_format: DT_Format = default_dt_format,
                        **kwargs: Any) -> None:
        """Issue start time message in a flower box.

        The start message includes the current datetime which is also saved to
        be used later to calculate the elapsed time for the *print_end_msg*
        invocation.

        Args:
            dt_format: Specifies the datetime format to use in the start
                         time message. The default is
                         StartStopHeader.default_dt_format.
            kwargs: Specifies the print arguments to use on the print
                      statement, such as *end*, *file*, or *flush*.

        :Example: Using StartStopHeader with start and end messages.

        >>> from scottbrian_utils.time_hdr import StartStopHeader

        >>> def func3() -> None:
        ...      print('2 + 2 =', 2+2)

        >>> hdr = StartStopHeader('func3')
        >>> hdr.print_start_msg()
        <BLANKLINE>
        **********************************************
        * Starting func3 on Mon Jun 29 2020 18:22:48 *
        **********************************************
        >>> func3()
        2 + 2 = 4
        >>> hdr.print_end_msg()
        <BLANKLINE>
        ********************************************
        * Ending func3 on Mon Jun 29 2020 18:22:50 *
        * Elapsed time: 0:00:00.001842             *
        ********************************************

        """
        self.start_DT = datetime.now()
        msg = 'Starting ' + self.func_name + ' on ' \
              + self.start_DT.strftime(dt_format)
        print_flower_box_msg([msg], **kwargs)


F = TypeVar('F', bound=Callable[..., Any])


@overload
def time_box(wrapped: F, *,
             dt_format: DT_Format = StartStopHeader.default_dt_format,
             time_box_enabled: Union[bool, Callable[..., bool]] = True,
             **kwargs: Any) -> F:
    r"""Overloaded time_box function.

    This overloaded function is needed strictly for mypy type checking.

    Note that there is a *wrapped* parameter for this overloaded
    function. This is the case where the time_box is called directly
    without using the pie decorator style. For example:
    def func(): pass
    func = time_box(func, dt_format = my_dt_format)

    What happens is the time_box call returns with a callable function that
    is the wrapped function. This new function is assigned to *func*. When
    *func* is called, the decorator function issues a starting time
    message, calls the wrapped function (i.e., the original *func*), issues
    the ending time message, and returns any return values that the wrapped
    function returns.

    Args:
        wrapped: Any callable function that accepts optional positional
                   and/or optional keyword arguments, and optionally returns a
                   value. The default is None, which will be the case when
                   the pie decorator version is used with any of the following
                   arguments specified.
        dt_format: Specifies the datetime format to use in the start
                     time message. The default is
                     StartStopHeader.default_dt_format.
        time_box_enabled: Specifies whether the start and end messages
                            should be issued (True) or not (False). The
                            default is True.
        kwargs: Specifies the print arguments to use on the print
                      statement, such as *end*, *file*, or *flush*.
    """


@overload
def time_box(*,
             dt_format: DT_Format = StartStopHeader.default_dt_format,
             time_box_enabled: Union[bool, Callable[..., bool]] = True,
             **kwargs: Any) -> Callable[[F], F]:
    """Overloaded time_box function.

    This overloaded function is needed strictly for mypy type checking.

    Note that there is no *wrapped* parameter for this overloaded
    function. This is the case where the time_box decorator call is coded as,
    for example:
    @time_box(dt_format = my_dt_format)
    def func(): pass

    This results in the equivalent of:
    def func(): pass
    func = time_box(dt_format = my_dt_format)(func)

    What happens is the time_box call returns with a callable function that
    specifies as input a callable, and this returned function is immediately
    called with *func* as the argument. This then results in the assignment
    of *func* to the decorator function that issues a starting time
    message, calls the wrapped function (i.e., the original *func*), issues
    the ending time message, and returns any return values that the wrapped
    function returns.

    Args:
        dt_format: Specifies the datetime format to use in the start
                     time message. The default is
                     StartStopHeader.default_dt_format.
        time_box_enabled: Specifies whether the start and end messages
                            should be issued (True) or not (False). The
                            default is True.
        kwargs: Specifies the print arguments to use on the print
                      statement, such as *end*, *file*, or *flush*.
    """


def time_box(wrapped: Optional[F] = None, *,
             dt_format: DT_Format = StartStopHeader.default_dt_format,
             time_box_enabled: Union[bool, Callable[..., bool]] = True,
             **kwargs: Any) -> F:
    """Decorator to wrap a function in start time and end time messages.

    The time_box decorator can be invoked with or without arguments, and the
    function being wrapped can optionally take arguments and optionally
    return a value. The wrapt.decorator is used to preserve the wrapped
    function introspection capabilities, and functools.partial is used to
    handle the case where decorator arguments are specified. The examples
    further below will help demonstrate the various ways in which the
    time_box decorator can be used.

    Args:
        wrapped: Any callable function that accepts optional positional
                   and/or optional keyword arguments, and optionally returns a
                   value. The default is None, which will be the case when
                   the pie decorator version is used with any of the following
                   arguments specified.
        dt_format: Specifies the datetime format to use in the start
                     time message. The default is
                     StartStopHeader.default_dt_format.
        time_box_enabled: Specifies whether the start and end messages
                            should be issued (True) or not (False). The
                            default is True.
        kwargs: Specifies the print arguments to use on the print
                      statement, such as *end*, *file*, or *flush*.

    Returns:
        A callable function that issues a starting time message, calls
        the wrapped function, issues the ending time message, and returns any
        return values that the wrapped function returns.


    :Example: statically wrapping function with time_box

    >>> from scottbrian_utils.time_hdr import time_box

    >>> _tbe = False

    >>> @time_box(time_box_enabled=_tbe)
    ... def func4a() -> None:
    ...      print('this is sample text for _tbe = False static example')

    >>> func4a()  # func4a is not wrapped by time box
    this is sample text for _tbe = False static example

    >>> _tbe = True

    >>> @time_box(time_box_enabled=_tbe)
    ... def func4b() -> None:
    ...      print('this is sample text for _tbe = True static example')

    >>> func4b()  # func4b is wrapped by time box
    <BLANKLINE>
    ***********************************************
    * Starting func4b on Mon Jun 29 2020 18:22:51 *
    ***********************************************
    this is sample text for _tbe = True static example
    <BLANKLINE>
    *********************************************
    * Ending func4b on Mon Jun 29 2020 18:22:51 *
    * Elapsed time: 0:00:00.000133              *
    *********************************************


    :Example: dynamically wrapping function with time_box:

    >>> from scottbrian_utils.time_hdr import time_box

    >>> _tbe = True
    >>> def tbe() -> bool: return _tbe

    >>> @time_box(time_box_enabled=tbe)
    ... def func5() -> None:
    ...      print('this is sample text for the tbe dynamic example')

    >>> func5()  # func5 is wrapped by time box
    <BLANKLINE>
    **********************************************
    * Starting func5 on Mon Jun 29 2020 18:22:51 *
    **********************************************
    this is sample text for the tbe dynamic example
    <BLANKLINE>
    ********************************************
    * Ending func5 on Mon Jun 29 2020 18:22:51 *
    * Elapsed time: 0:00:00.000130             *
    ********************************************

    >>> _tbe = False
    >>> func5()  # func5 is not wrapped by time_box
    this is sample text for the tbe dynamic example


    :Example: specifying a datetime format:

    >>> from scottbrian_utils.time_hdr import time_box

    >>> aDatetime_format: DT_Format = DT_Format('%m/%d/%y %H:%M:%S')
    >>> @time_box(dt_format=aDatetime_format)
    ... def func6() -> None:
    ...     print('this is sample text for the datetime format example')

    >>> func6()
    <BLANKLINE>
    ***************************************
    * Starting func6 on 06/30/20 17:07:48 *
    ***************************************
    this is sample text for the datetime format example
    <BLANKLINE>
    *************************************
    * Ending func6 on 06/30/20 17:07:48 *
    * Elapsed time: 0:00:00.000073      *
    *************************************

    """
    # ========================================================================
    #  The following code covers cases where time_box is used with or without
    #  parameters, and where the decorated function has or does not have
    #  parameters.
    #
    #     Here's an example of time_box without args:
    #         @time_box
    #         def aFunc():
    #             print('42')
    #
    #     This is what essentially happens under the covers:
    #         def aFunc():
    #             print('42')
    #         aFunc = time_box(aFunc)
    #
    #     In fact, the above direct call can be coded as shown instead of using
    #     the pie decorator style.
    #
    #     Here's an example of time_box with args:
    #         @time_box(end='\n\n')
    #         def aFunc():
    #             print('42')
    #
    #     This is what essentially happens under the covers:
    #         def aFunc():
    #             print('42')
    #         aFunc = time_box(end='\n\n')(aFunc)
    #
    #     Note that this is a bit more tricky: time_box(end='\n\n') portion
    #     results in a function being returned that takes as its first
    #     argument the separate aFunc specification in parens that we see at
    #     the end of the first portion.
    #
    #     Note that we can also code the above as shown and get the same
    #     result.
    #
    #     Also, we can code the following and get the same result:
    #         def aFunc():
    #             print('42')
    #         aFunc = time_box(aFunc, end='\n\n')
    #
    #     What happens in the tricky case is time_box gets control and tests
    #     whether aFunc was specified, and if not returns a call to
    #     functools.partial which is the function that accepts the aFunc
    #     specification and then calls time_box with aFunc as the first
    #     argument with the end='\n\n' as the second argument as we now have
    #     something that time_box can decorate.
    #
    #     One other complication is that we are also using the wrapt.decorator
    #     for the inner wrapper function which does some more smoke and
    #     mirrors to ensure introspection will work as expected.
    # ========================================================================

    if wrapped is None:
        return cast(F, functools.partial(time_box, dt_format=dt_format,
                                         time_box_enabled=time_box_enabled,
                                         **kwargs))

    @decorator(enabled=time_box_enabled)  # type: ignore
    def wrapper(func_to_wrap: F, instance: Optional[Any],
                args: Tuple[Any, ...],
                kwargs2: Dict[str, Any]) -> Any:
        header = StartStopHeader(func_to_wrap.__name__)
        header.print_start_msg(dt_format=dt_format, **kwargs)

        ret_value = func_to_wrap(*args, **kwargs2)

        header.print_end_msg(dt_format=dt_format, **kwargs)

        return ret_value

    return cast(F, wrapper(wrapped))
