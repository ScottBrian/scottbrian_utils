"""Module throttle.

========
Throttle
========

Use the Throttle class to limit the number of requests made during a permitted
interval. Many internet services state s limit of how many requests you can
make per some time interval. For example, no more than one request per second,
or maybe something like no mpore than 30 requests each minute. The Throttle
class allows you to stay with the limit.

:Example: make requests to a service with a one request per second limit

In the example code below, the call to before_request will check to make sure
we are within the allowed limit. After the request is made and returns, the
call to after_request will save the time the request was made. Upon iteration,
before_request will now see that a request was just made and will wait for
just enough to ensure we do not make the next request too soon.

>>> from scottbrian_utils.throttle import Throttle
>>> import time
>>> request_throttle = Throttle(num_requests_allowed=1, per_seconds=1)
>>> for i in range(100):
>>>     request_throttle.before_request()
>>>     time.sleep(.1)  # simulate request that takes 1/10 second
>>>     request_throttle.after_request()


Example: make requests to a service with a 20 request per minute limit

In this second example, we are allowing up to 20 requests per minute. In this
case, the before_request method will allow the first 20 requests to go through
without waiting. When the 21st request is made, before_request will wait to
ensure we remain within the limit. More specifically, with each request being
made  approximately every .1 seconds, the first 20 request took approximately 2
seconds. Thus, before_request will wait for 58 seconds before allowing the
21st request to proceed.

>>> from scottbrian_utils.throttle import Throttle
>>> import time
>>> request_throttle = Throttle(num_requests_allowed=20, per_seconds=60)
>>> for i in range(100):
>>>     request_throttle.before_request()
>>>     time.sleep(.1)  # simulate request that takes 1/10 second
>>>     request_throttle.after_request()

As can be seen with the above example, we were able to allow a burst of
requests and still remain with the limit. A simpler approach would wait 1/3
second between each request to ensure no more than 20 requess per minute, but
that would penalize a case where a burst of less than 20 requests are made,
and then we go do some other processing for a couple of minutes, and then
make another burst of requests.

The throttle module contains:

    1) Throttle class with before_request and after_request methods.
    2) Error exception classes:

       a. IncorrectNumberRequestsSpecified
       b. IncorrectPerSecondsSpecified

"""
from collections import deque
from pathlib import Path
from typing import Type, TYPE_CHECKING


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
                 num_requests_allowed: int,
                 per_seconds: float
                 ) -> None:
        """Initialize an instance of the Throttle class.

        Args:
            num_requests_allowed: The number of requests that can be made in
                                    the interval specified by per_seconds.
            per_seconds: The number of seconds in which the number of requests
                           specified in num_requests_allowed can be made.

        Raises:
            IncorrectNumberRequestsSpecified: The num_requests_allowed
                                                specification must be
                                                a positive integer greater than
                                                zero.

            IncorrectPerSecondsSpecified: The per_seconds specification must be
                                            a positive int or float greater
                                            than zero.

        :Example: instantiate a throttle for 1 request per second

        >>> from scottbrian_utils.throttle import Throttle
        >>> request_throttle = Throttle(num_requests_allowed=1, per_seconds=1)

        :Example: instantiate a throttle for 5 requests per 1/2 second

        >>> from scottbrian_utils.throttle import Throttle
        >>> request_throttle = Throttle(num_requests_allowed=5,
        ...                             per_seconds=0.5)

        :Example: instantiate a throttle for 20 requests per 2 minutes

        >>> from scottbrian_utils.throttle import Throttle
        >>> request_throttle = Throttle(num_requests_allowed=5,
        ...                             per_seconds=120)

        """
        if (isinstance(num_requests_allowed, int)
                and (0 < num_requests_allowed)):
            self.num_requests_allowed = num_requests_allowed
        else:
            raise IncorrectNumberRequestsSpecified('The num_requests_allowed '
                                                   'specification must be a '
                                                   'positive integer greater '
                                                   'than zero.')
        if ((isinstance(per_seconds, float) or isinstance(per_seconds, int))
                and (0 < per_seconds)):
            self.per_seconds = per_seconds
        else:
            raise IncorrectPerSecondsSpecified('The per_seconds specification '
                                               'must be a positive int or '
                                               'float greater than zero.')
        self.request_times = deque()

    def __len__(self) -> int:
        """Return the number of items in the request_times deque.

        Returns:
            The number of entries in the request_times deque as an integer

        :Example: instantiate a throttle for 10 requests per 1 minute

        >>> from scottbrian_utils.throttle import Throttle
        >>> import time
        >>> request_throttle = Throttle(num_requests_allowed=10,
        ...                             per_seconds=60)
        >>> for i in range(7):
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
        >>> request_throttle = Throttle(num_requests_allowed=30,
        ...                             per_seconds=30)
        >>> repr(request_throttle)
        Throttle(num_requests_allowed=30, per_seconds=30)

        """
        if TYPE_CHECKING:
            __class__: Type[Throttle]
        classname = self.__class__.__name__
        parms = f'num_requests_allowed={self.num_requests_allowed}, ' \
                f'per_seconds={self.per_seconds}'

        return f'{classname}({parms})'

    def before_request(self) -> None:
        """Wait if needed to remain within the specified limit.

        :Example: instantiate a throttle for 10 requests per 5 seconds

        >>> from scottbrian_utils.throttle import Throttle
        >>> import time
        >>> request_throttle = Throttle(num_requests_allowed=10, per_seconds=5)
        >>> for i in range(100):
        >>>     request_throttle.before_request()
        >>>     time.sleep(.1)  # simulate request that takes 1/10 second
        >>>     request_throttle.after_request()

        """
        pass

    def after_request(self) -> None:
        """Add the current time to the request_times deque.

        :Example: instantiate a throttle for 1 request per 10 seconds

        >>> from scottbrian_utils.throttle import Throttle
        >>> import time
        >>> request_throttle = Throttle(num_requests_allowed=6, per_seconds=10)
        >>> for i in range(10):
        >>>     request_throttle.before_request()
        >>>     time.sleep(.1)  # simulate request that takes 1/10 second
        >>>     request_throttle.after_request()

        """
        pass
