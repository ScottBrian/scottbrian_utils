"""Module throttle.

========
Throttle
========

You can use the @throttle decorator to limit the number of requests made
during a specific interval. Many online services state a limit as to how many
requests can be made per some time interval. For example, "no more than one
request per second", or maybe something like "no more than 30 requests each
minute". The @throttle decorator wraps a method that makes requests to ensure
that the the limit is not exceeded. The @throttle keeps track of the time for
each request and will insert a wait (via time.sleep()) as needed to stay within
the limit. Note that the Throttle class provides the same service to allow
you to use the throttle where a decorator is not the optimal choice. Following
are examples of using both the @throttle decorator and the Throttle class
methods.

:Example: use @throttle decorator for a limit of one request per second

In the example code below, in the first iteration, the @throttle
decorator code will see that there are no requests that have been made within
the last second and will allow the request to proceed. On the next iteration,
the @throttle code will wait until the first request has aged out and then
allow the second request to proceed. This will continue with a wait before
each request to ensure the limit is not exceeded.

>>> from scottbrian_utils.throttle import Throttle
>>> import time
>>> @throttle(requests=1, seconds=1)
>>> def make_request():
...     time.sleep(.1)  # simulate request that takes 1/10 second
>>> for i in range(100):
...     make_request()


:Example: use Throttle methods for a limit of one request per second

In the example code below, the call to before_request will check to make sure
we are within the allowed limit. After the request is made and returns, the
call to after_request will save the time the request was made. Upon iteration,
before_request will now see that a request was just made and will wait for
just enough time to ensure we do not make the next request too soon.

>>> from scottbrian_utils.throttle import Throttle
>>> import time
>>> request_throttle = Throttle(requests=1, seconds=1)
>>> for i in range(100):
...     request_throttle.before_request()
...     time.sleep(.1)  # simulate request that takes 1/10 second
...     request_throttle.after_request()


Example: use @throttle decorator for a limit of 20 requests per minute

In this example, we are allowing up to 20 requests per minute. In this case
the @throttle decorator code will allow the first 20 requests to go through
without waiting. When the 21st request is made, the @throttle code will wait to
ensure we remain within the limit. More specifically, with each request being
made approximately every .1 seconds, the first 20 request took approximately 2
seconds. Thus, @throttle code will wait for 58 seconds before allowing the
21st request to proceed.

>>> from scottbrian_utils.throttle import Throttle
>>> import time
>>> @throttle(requests=20, seconds=60)
>>> def make_request():
...     time.sleep(.1)  # simulate request that takes 1/10 second
>>> for i in range(100):
...     make_request()

Example: use Throttle methods for a limit of 20 requests per minute

In this example, we are allowing up to 20 requests per minute. In this case
the before_request method will allow the first 20 requests to go through
without waiting. When the 21st request is made, before_request will wait to
ensure we remain within the limit. More specifically, with each request being
made approximately every .1 seconds, the first 20 request took approximately 2
seconds. Thus, before_request will wait for 58 seconds before allowing the
21st request to proceed.

>>> from scottbrian_utils.throttle import Throttle
>>> import time
>>> request_throttle = Throttle(requests=20, seconds=60)
>>> for i in range(100):
>>>     request_throttle.before_request()
>>>     time.sleep(.1)  # simulate request that takes 1/10 second
>>>     request_throttle.after_request()

As can be seen with the above examples, we were able to allow a burst of
20 requests and still remain within the limit. A simpler approach would wait
1/3 second between each request to ensure no more than 20 requess per minute,
but that would penalize a case where a burst of less than 20 requests are made,
and then we go do some other processing for a couple of minutes, and then
make another burst of requests.

The throttle module contains:

    1) Throttle class with before_request and after_request methods.
    2) Error exception classes:

       a. IncorrectNumberRequestsSpecified
       b. IncorrectPerSecondsSpecified
    3) @throttle decorator

"""
import time
from collections import deque
from datetime import datetime, timedelta
from typing import (Any, Callable, cast, Dict, Optional, Tuple, Type,
                    TYPE_CHECKING, TypeVar, Union)
import functools
from wrapt.decorators import decorator  # type: ignore


class ThrottleError(Exception):
    """Base class for exceptions in this module."""
    pass


class IncorrectNumberRequestsSpecified(ThrottleError):
    """FileCatalog exception for an incorrect file_specs specification."""
    pass


class IncorrectPerSecondsSpecified(ThrottleError):
    """FileCatalog exception attempted add of existing but different path."""
    pass


class Throttle:
    """Provides a throttle mechanism.

    The Throttle class is used to throttle the number of requests being made
    to prevent going over a specified limit.
    """

    def __init__(self,
                 requests: int,
                 seconds: Union[int, float]
                 ) -> None:
        """Initialize an instance of the Throttle class.

        Args:
            requests: The number of requests that can be made in
                                    the interval specified by seconds.
            seconds: The number of seconds in which the number of requests
                           specified in requests can be made.

        Raises:
            IncorrectNumberRequestsSpecified: The requests
                                                specification must be
                                                a positive integer greater than
                                                zero.
            IncorrectPerSecondsSpecified: The seconds specification must be
                                            a positive int or float greater
                                            than zero.

        :Example: instantiate a throttle for 1 request per second

        >>> from scottbrian_utils.throttle import Throttle
        >>> request_throttle = Throttle(requests=1, seconds=1)

        :Example: instantiate a throttle for 5 requests per 1/2 second

        >>> from scottbrian_utils.throttle import Throttle
        >>> request_throttle = Throttle(requests=5,
        ...                             seconds=0.5)

        :Example: instantiate a throttle for 20 requests per 2 minutes

        >>> from scottbrian_utils.throttle import Throttle
        >>> request_throttle = Throttle(requests=5,
        ...                             seconds=120)

        """
        if (isinstance(requests, int)
                and (0 < requests)):
            self.requests = requests
        else:
            raise IncorrectNumberRequestsSpecified('The requests '
                                                   'specification must be a '
                                                   'positive integer greater '
                                                   'than zero.')
        if ((isinstance(seconds, float) or isinstance(seconds, int))
                and (0 < seconds)):
            self.seconds = timedelta(seconds=seconds)
        else:
            raise IncorrectPerSecondsSpecified('The seconds specification '
                                               'must be a positive int or '
                                               'float greater than zero.')
        self.request_times = deque()

    def __len__(self) -> int:
        """Return the number of items in the request_times deque.

        Returns:
            The number of entries in the request_times deque as an integer

        The call to the Throttle after_request method adds a timestamp to
        its deque and the call to the Throttle before_request removes any of
        those timestamps that have aged out per the seconds instantiation
        argument. Thus, the len of Throttle depends on whatever timestamnps
        are on the deque that have not yet been removed by a call to
        before_request.

        :Example: instantiate a throttle for 10 requests per 1 minute

        >>> from scottbrian_utils.throttle import Throttle
        >>> import time
        >>> request_throttle = Throttle(requests=10,
        ...                             seconds=60)
        >>> for i in range(7):  # quickly add 6 timestamps to throttle deque
        >>>     request_throttle.before_request()
        >>>     time.sleep(.1)  # simulate request that takes 1/10 second
        >>>     request_throttle.after_request()
        >>> print(len(request_throttle))
        6

        """
        return len(self.request_times)

    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example: instantiate a throttle for 30 requests per 1/2 minute

         >>> from scottbrian_utils.throttle import Throttle
        >>> request_throttle = Throttle(requests=30,
        ...                             seconds=30)
        >>> repr(request_throttle)
        Throttle(requests=30, seconds=30)

        """
        if TYPE_CHECKING:
            __class__: Type[Throttle]
        classname = self.__class__.__name__
        parms = f'requests={self.requests}, ' \
                f'seconds={self.seconds}'

        return f'{classname}({parms})'

    def before_request(self) -> None:
        """Wait if needed to remain within the specified limit.

        :Example: instantiate a throttle for 10 requests per 5 seconds

        >>> from scottbrian_utils.throttle import Throttle
        >>> import time
        >>> request_throttle = Throttle(requests=10, seconds=5)
        >>> for i in range(30):  # try to push us over the limit
        >>>     request_throttle.before_request()
        >>>     time.sleep(.1)  # simulate request that takes 1/10 second
        >>>     request_throttle.after_request()

        """
        #######################################################################
        # trim the deque of aged out timestamps
        #######################################################################
        trim_time = datetime.utcnow() - self.seconds
        while len(self.request_times) > 0:
            if self.request_times[0] < trim_time:
                self.request_times.popleft()
            else:  # all remaining times are still ahead of trim_time
                break
        #######################################################################
        # wait if we are at limit
        #######################################################################
        # note: in the next line, we should never find more than allowed
        if len(self.request_times) >= self.requests:
            time.sleep((self.request_times[0] - trim_time).total_seconds())

    def after_request(self) -> None:
        """Add the current time to the request_times deque.

        :Example: instantiate a throttle for 1 request per 10 seconds

        >>> from scottbrian_utils.throttle import Throttle
        >>> import time
        >>> request_throttle = Throttle(requests=6, seconds=10)
        >>> for i in range(20):  # try to push us over the limit
        >>>     request_throttle.before_request()
        >>>     time.sleep(.1)  # simulate request that takes 1/10 second
        >>>     request_throttle.after_request()

        """
        self.request_times.append(datetime.utcnow())


F = TypeVar('F', bound=Callable[..., Any])


def throttle(wrapped: Optional[F] = None, *,
             requests: int,
             seconds: Union[int, float],
             throttle_enabled: Union[bool, Callable[..., bool]] = True) -> F:
    """Decorator to wrap a function in a throttle to avoid exceeding a limit.

    The throttle wraps code around a function that is typically used to issue
    requests to an online service. The throttle code is used to limit the
    number of requests that are made to ensure it does not exceed a limit as
    stated by the service. The limit is typically stated as being some number
    of requests per some time interval. The throttle limits are spoecified via
    the *request* and *seconds* arguments. The default is 1 request per second.

    The throttle decorator can be invoked with or without arguments, and the
    function being wrapped can optionally take arguments and optionally
    return a value. The wrapt.decorator is used to preserve the wrapped
    function introspection capabilities, and functools.partial is used to
    handle the case where decorator arguments are specified. The examples
    further below will help demonstrate the various ways in which the
    throttle decorator can be used.

    Args:
        wrapped: Any callable function that accepts optional positional
                   and/or optional keyword arguments, and optionally returns a
                   value. The default is None, which will be the case when
                   the pie decorator version is used with any of the following
                   arguments specified.
        requests: Number of requests that are allowed per the *seconds*
                    specification.
        seconds: Number of seconds in which the number of requests specified
                   by *requests* can be made.
        throttle_enabled: Specifies whether the start and end messages
                            should be issued (True) or not (False). The
                            default is True.

    Returns:
        A callable function that checks and waits if necessary to stay within
        the limit, calls the wrapped function, saves the time of the call to
        be used later to check the limit, and returns any return values that
        the wrapped function returns.

    :Example: statically wrapping function with throttle

    >>> from scottbrian_utils.throttle import throttle

    >>> _tbe = False

    >>> @throttle(requests=1, seconds=1, throttle_enabled=_tbe)
    ... def func4a() -> None:
    ...      print('this is sample text for _tbe = False static example')

    >>> func4a()  # func4a is not wrapped by throttle
    this is sample text for _tbe = False static example

    >>> _tbe = True

    >>> @throttle(requests=1, seconds=1, throttle_enabled=_tbe)
    ... def func4b() -> None:
    ...      print('this is sample text for _tbe = True static example')

    >>> func4b()  # func4b is wrapped by throttle
    this is sample text for _tbe = True static example


    :Example: dynamically wrapping function with throttle:

    >>> from scottbrian_utils.throttle import throttle

    >>> _tbe = True
    >>> def tbe() -> bool: return _tbe

    >>> @throttle(requests=1, seconds=1, throttle_enabled=tbe)
    ... def func5() -> None:
    ...      print('this is sample text for the tbe dynamic example')

    >>> func5()  # func5 is wrapped by throttle
    this is sample text for the tbe dynamic example


    >>> _tbe = False
    >>> func5()  # func5 is not wrapped by throttle
    this is sample text for the tbe dynamic example


    """
    # ========================================================================
    #  The following code covers cases where throttle is used with or without
    #  parameters, and where the decorated function has or does not have
    #  parameters.
    #
    #     Here's an example of throttle without args:
    #         @throttle
    #         def aFunc():
    #             print('42')
    #
    #     This is what essentially happens under the covers:
    #         def aFunc():
    #             print('42')
    #         aFunc = throttle(aFunc)
    #
    #     In fact, the above direct call can be coded as shown instead of using
    #     the pie decorator style.
    #
    #     Here's an example of throttle with args:
    #         @throttle(end='\n\n')
    #         def aFunc():
    #             print('42')
    #
    #     This is what essentially happens under the covers:
    #         def aFunc():
    #             print('42')
    #         aFunc = throttle(end='\n\n')(aFunc)
    #
    #     Note that this is a bit more tricky: throttle(end='\n\n') portion
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
    #         aFunc = throttle(aFunc, end='\n\n')
    #
    #     What happens in the tricky case is throttle gets control and tests
    #     whether aFunc was specified, and if not returns a call to
    #     functools.partial which is the function that accepts the aFunc
    #     specification and then calls throttle with aFunc as the first
    #     argument with the end='\n\n' as the second argument as we now have
    #     something that throttle can decorate.
    #
    #     One other complication is that we are also using the wrapt.decorator
    #     for the inner wrapper function which does some more smoke and
    #     mirrors to ensure introspection will work as expected.
    # ========================================================================

    if wrapped is None:
        return cast(F, functools.partial(throttle,
                                         requests=requests,
                                         seconds=seconds,
                                         throttle_enabled=throttle_enabled))

    @decorator(enabled=throttle_enabled)  # type: ignore
    def wrapper(func_to_wrap: F, instance: Optional[Any],
                args: Tuple[Any, ...],
                kwargs2: Dict[str, Any]) -> Any:
        a_throttle = Throttle(requests=requests,
                              seconds=seconds)
        a_throttle.before_request()
        ret_value = func_to_wrap(*args, **kwargs2)
        a_throttle.after_request()

        return ret_value

    return cast(F, wrapper(wrapped))
