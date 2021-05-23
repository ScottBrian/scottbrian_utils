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
import threading, queue

from datetime import datetime, timedelta
from typing import (Any, Callable, cast, Dict, Final, NamedTuple, Optional,
                    Tuple, Type, TYPE_CHECKING, TypeVar, Union)
import functools
from wrapt.decorators import decorator  # type: ignore


class ThrottleError(Exception):
    """Base class for exceptions in this module."""
    pass


class IncorrectRequestsSpecified(ThrottleError):
    """Throttle exception for an incorrect requests specification."""
    pass


class IncorrectSecondsSpecified(ThrottleError):
    """Throttle exception for an incorrect seconds specification."""
    pass


class IncorrectModeSpecified(ThrottleError):
    """Throttle exception for an incorrect mode specification."""
    pass


class IncorrectShutdownCheckSpecified(ThrottleError):
    """Throttle exception for an incorrect shutdown_check specification."""
    pass


class AttemptedSyncRequestInAsyncMode(ThrottleError):
    """Throttle exception for sync request with async mode throttle."""
    pass


class Throttle:
    """Provides a throttle mechanism.

    The Throttle class is used to throttle the number of requests being made
    to prevent going over a specified limit.
    """

    class Request(NamedTuple):
        """NamedTuple for the request queue item."""
        request_func: Callable[..., Any]
        args: Tuple[Any,]
        kwargs: Dict[str, Any]

    ASYNC_MODE: Final[int] = 1
    SYNC_MODE_EC: Final[int] = 2
    SYNC_MODE_LB: Final[int] = 3



    def __init__(self, *,
                 requests: int,
                 seconds: Union[int, float],
                 mode: int,
                 early_count: Optional[int] = None,
                 lb_threshold: Optional[Union[int, float]] = None,
                 shutdown_check: Optional[Callable[[], bool]] = None
                 ) -> None:
        """Initialize an instance of the Throttle class.

        Args:
            requests: The number of requests that can be made in
                        the interval specified by seconds.
            seconds: The number of seconds in which the number of requests
                       specified in requests can be made.
            mode: Specifies whether to perform asynchronous throttling or
                    synchronous throttling. With asynchoneous throttling,
                    each request is placed on a queue and control returns
                    to the caller. A separate thread then executes each
                    request at a steady interval to acheieve the specified
                    number of requests per the specified number of seconds.
                    Since the caller is given back control, any return
                    values from the request must be handled by an
                    established protocol between the caller and the request,
                    (e.g., a callback method). Asynchronous mode is requested
                    by specifying a mode value of 1 (Throttle.ASYNC_MODE).
                    For synchronous throttling, the caller may be blocked to
                    delay the request in order to achieve the the specified
                    number of requests per the specified number of seconds.
                    Since the request is handled synchronously on the same
                    thread, any return value from the request will be
                    immediately returned to the caller when the request
                    completes.
                    The synchronous processing can employ one of two
                    different algorithms that can provide flexability to
                    the caller be allowing some number of requests to
                    proceed without delay. The first is the early arrival count
                    algorithm, specified with a mode value of 2
                    (Throttle.SYNC_MODE_EC) and an early_count value. The other
                    algorithm is the leaky bucket algorithm, specified with
                    a mode value of 3 (Throttle.SYNC_MODE_LB) and an
                    lb_threshold value.
            early_count: Specifies the number of requests that are allowed
                           to proceed that arrive earlier than the
                           allowed interval. The count of early requests
                           is incemented, and when it exceeds the
                           early_count, the request will be delayed to
                           align it with its expected arrival time. Any
                           request that arrives at or beyond the
                           allowed interval will cause the count to be
                           reset (included the request that was delayed
                           since it will now be sent at the allowed interval).
                           A specification of zero for the early_count will
                           effectively cause all requests that are early to
                           be delayed.
            lb_threshold: Specifies the threshold for the leaky bucket when
                            Throttle.SYNC_MODE_LB is specified for mode.
                            This is the number of requests that can be in
                            the bucket such that the next request is allowed
                            to proceed without delay. That request is
                            added to the bucket, and then the bucket leaks
                            out the requests. When the next request arrives,
                            it will be delayed by whatever amount of time is
                            needed for the bucket to have leaked enough to be
                            at the threshold. A specification of zero for the
                            lb_threshold will effectively cause all requests
                            that are early to be delayed.
            shutdown_check: The client method to call to determine whether the
                              throttle should reject any additional requests
                              for async mode and clean up the queue by
                              scheduling the remaining request items
                              immediately without delay. This method must
                              not take arguments, and must return a bool.
                              Note that the client will most likely need a
                              proper protocol for shutdown such that its
                              request code recognizes when shutdown is in
                              progress. For example, instead of calling the
                              service, the request could call its callback
                              method with a code to signify that shutdown is in
                              progress. This may be needed, for example,
                              in the case where the client is waiting on an
                              event from its callback method. The
                              shutdown_check is optional. An alternative is
                              to call start_shutdown to get the same result,
                              or to do nothing if the client design calls for
                              it.


        Raises:
            IncorrectRequestsSpecified: The requests specification must be
                                          a positive integer greater than
                                          zero.
            IncorrectSecondsSpecified: The seconds specification must be
                                         a positive int or float greater
                                         than zero.
            IncorrectModeSpecified: The mode specification must be an
                                       integer with value 1 or 2.
            IncorrectShutdownCheckSpecified: The shutdown_check specification,
                                               when supplied, must be a
                                               function.


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
            raise IncorrectRequestsSpecified('The requests '
                                              'specification must be a '
                                              'positive integer greater '
                                              'than zero.')
        if isinstance(seconds, (int, float)) and (0 < seconds):
            self.seconds = timedelta(seconds=seconds)
        else:
            raise IncorrectSecondsSpecified('The seconds specification '
                                            'must be a positive int or '
                                            'float greater than zero.')

        if (isinstance(mode, int)
                and mode in (Throttle.ASYNC_MODE, Throttle.SYNC_MODE_LB,
                             Throttle.SYNC_MODE_EC)):
            self.mode = mode
        else:
            raise IncorrectModeSpecified('The mode specification must be an '
                                          'integer with value 1 or 2.')

        if shutdown_check:
            if callable(shutdown_check):
                self.shutdown_check = shutdown_check
            else:
                raise IncorrectShutdownCheckSpecified('The shutdown_check '
                                                      'specification, when'
                                                      'supplied, must be a '
                                                      'function')
        else:
            self.shutdown_check = None

        self._interval = 0
        self.wait_seconds = seconds/requests
        self.request_times = deque()
        self.request_q = queue.Queue(maxsize=self.burst)
        self.schedule_requests_lock = threading.Lock()
        self._shutdown = False
        self._expected_arrival_time = 0
        self._leaky_bucket_tolerance = 0
        self._early_arrival_count = 0
        self._allowed_early_arrivals = 0

        if mode == Throttle.ASYNC_MODE:
            self.request_scheduler_thread = \
                threading.Thread(target=self.schedule_requests)
            self.request_scheduler_thread.start()
        else:
            self.request_scheduler_thread = None

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
                f'seconds={self.seconds.total_seconds()}'

        return f'{classname}({parms})'

    @property
    def shutdown(self) -> bool:
        """Determine whether we need to shutdown.

        Returns:
            True if we need to start shutdown processing, False otherwise
        """
        # If client provided a shutdown_check func and it returns true,
        # set self._shutdown to True.
        # Note that self._shutdown is initialized to False, and once
        # shutdown_check returns True we set self._shutdown to True
        # and never back to False.
        if self.shutdown_check and self.shutdown_check():
            self._shutdown = True
        return self._shutdown

    def start_shutdown(self) -> None:
        """Shutdown the throttle request scheduling.

        Raises:
            AttemptedShutdownForSyncThrottle: Calling start_shutdown is only
                                                valid for a throttle
                                                instantiated with a mode of
                                                Throttle.MODE_ASYNC                                             shutthe shutdown
        """
        self._shutdown = True  # indicate shutdown in progress
        if self.mode == Throttle.ASYNC_MODE:
            self.request_scheduler_thread.join()  # wait for scheduler cleanup

    def send_request(self,
                     func: Callable[..., Any],
                     *args: Any,
                     **kwargs: Any
                     ) -> Any:
        """Send the request.

        Args:
            func: the request function to be run
            args: the request function positional arguments
            kwargs: the request function keyword arguments

        Returns:
              The return code from the request function (may be None)

        """
        #######################################################################
        # ASYNC_MODE
        #######################################################################
        if self.mode == Throttle.ASYNC_MODE:
            request_item = Throttle.Request(func, args, kwargs)

            while not self.shutdown:
                try:
                    self.request_q.put(request_item, block=True, timeout=1)
                except queue.Full:
                    continue  # no need to wait since we already did

                ###################################################################
                # There is a possibility that shutdown was switched to True
                # and the schedule_requests method saw that and cleaned up the
                # queue and exited BEFORE we were able to queue our request. In
                # that case, we need to deal with that here by simply calling
                # schedule_requests and run our new request from this thread.
                ###################################################################
                if not self.shutdown and not self.request_q.empty():
                    self.schedule_requests()
            return
        #######################################################################
        # SYNC_MODE
        #######################################################################
        else:
            arrival_time = time.time()  # time that this request is being made

            ###################################################################
            # The Throttle class can be instantiated for sync requests using
            # either the leaky bucket algo or by specifying the number of
            # early requests allowed. If the leaky bucket algo is being used,
            # self._leaky_bucket_tolerance will be a positive non_zero value.
            # If, instead, the early requests allowed technique is being used,
            # self._early_arrival_count will be a positive non-zero value.
            # The following code handles either one case or the other,
            # whichever one was decided by the user when the class was
            # instantiated.
            ###################################################################

            if self.mode == Throttle.SYNC_MODE_EC:  # early count algo
                if arrival_time < self._expected_arrival_time:  # if early
                    # bump count of early arrivals without an intervening wait
                    self._early_arrival_count += 1

                    # if we exceed the allowed early arrivals, delay the
                    # request
                    if (self._allowed_early_arrivals <
                            self._early_arrival_count):
                        self._early_arrival_count = 0  # reset the count
                        wait_time = self._expected_arrival_time - arrival_time
                        time.sleep(wait_time)
            else:  # leaky bucket algo
                if arrival_time < (self._expected_arrival_time -
                                   self._leaky_bucket_tolerance):  # if early
                    # calculate wait time such that the wait will bring the
                    # request within tolerance and not be early
                    wait_time = (self._expected_arrival_time -
                                 self._leaky_bucket_tolerance - arrival_time)
                    time.sleep(wait_time)

            # The caller should protect the function with a try and either
            # raise an exception or pass back a return value that makes sense.
            # Putting a try around the call here and raising an exception
            # might not be what the caller wants.
            ret_value = func(*args, **kwargs)  # make the request

            # Update the expected arrival time for the next request by
            # adding the request interval to our current time. Note that we
            # use the current time instead of the arrival time to make sure we
            # account for any processing delays while trying to get the
            # request to the service who is then observing arrival times at
            # its point or arrival, not ours. If we were to use our arrival
            # time to update the next expected arrival time, we face a
            # possible scenario where we send a request that gets delayed
            # en route to the service, but out next request arrives at the
            # updated expected arrival time and is sent out immediately, but it
            # now arrives early relative to the previous request, as observed
            # by the service. By using the current time, we avoid that
            # scenario. It does mean, however, that any built in constant
            # delays in sending the request will be adding an extra amount of
            # time to our calculated interval with the undesirable effect
            # that all requests will now be throttled more than they need to
            # be.
            # TODO: subtract the constant path delay from the interval
            self._expected_arrival_time = (max(time.time(),
                                               self._expected_arrival_time)
                                           + self._interval)

            return ret_value  # return the request return value (might be None)

    def schedule_requests(self) -> None:
        """Get tasks from queue and run them."""
        # Requests will be scheduled from the request_q at the interval
        # calculated from the requests and seconds arguments when the
        # throttle was instantiated. If shutdown is indicated,
        # the request_q will be cleaned up with any remaining requests
        # dropped. Note that request_q.get will only wait for a second so
        # we can detect shutdown in a timely fashion.
        with self.schedule_requests_lock:
            while not self.shutdown or not self.request_q.empty():
                try:
                    request_item = self.request_q.get(block=True, timeout=1)
                except queue.Empty:
                    continue  # no need to wait since we already did
                ###############################################################
                # call the request function
                # if shutdown indicated, drop requests
                ###############################################################
                if not self.shutdown:
                    request_item.request_func(*request_item.args,
                                              **request_item.kwargs)
                self.request_q.task_done()

                ###############################################################
                # wait (i.e., throttle)
                # Note that the wait time could be anywhere from a fraction of
                # a second to several seconds. We want to be responsive in
                # case we need to bail for shutdown, so we wait in 1 second
                # or less increments and bail if we detect shutdown.
                ###############################################################
                wait_seconds = self.wait_seconds  # could be small or large
                while wait_seconds > 0 and not self.shutdown:
                    time.sleep(min(1, wait_seconds))
                    wait_seconds = wait_seconds - 1

    # def _send_sync(self,
    #                func: Callable[[...], None],
    #                *,
    #                args: Optional[Tuple[Any, ...]] = (),
    #                kwargs: Optional[Dict['str', Any]] = None
    #                ) -> Any:
    #     """Send the request synchronously, possibly delayed.
    #
    #     Args:
    #         func: the request function to be run
    #         args: the request function positional arguments
    #         kwargs: the request function keyword arguments
    #
    #     Returns:
    #           The return code from the request function (may be None)
    #
    #     Raises:
    #           AttemptedSyncRequestInAsyncMode: The send_sync method was
    #                                              called for a Throttle that
    #                                              was instantiated with a mode
    #                                              mode of 1 for asynchronous
    #                                              requests.
    #
    #     """
    #     arrival_time = time.time()  # time that this request is being made
    #
    #     #######################################################################
    #     # The Throttle class can be instantiated for sync requests using
    #     # either the leaky bucket algo or by specifying the number of
    #     # early requests allowed. If the leaky bucket algo is being used,
    #     # self._leaky_bucket_tolerance will be a positive non_zero value.
    #     # If, instead, the early requests allowed technique is being used,
    #     # self._early_arrival_count will be a positive non-zero value.
    #     # The following code handles either one case or the other, whichever
    #     # one was decided by the user when the class was instantiated.
    #     #######################################################################
    #
    #     if self.mode == Throttle.SYNC_MODE_EC:  # early count algo
    #         if arrival_time < self._expected_arrival_time:  # if early
    #             # bump count of early arrivals without an intervening wait
    #             self._early_arrival_count += 1
    #
    #             # if we exceed the allowed early arrivals, delay the request
    #             if self._allowed_early_arrivals < self._early_arrival_count:
    #                 self._early_arrival_count = 0  # reset the count
    #                 wait_time = self._expected_arrival_time - arrival_time
    #                 time.sleep(wait_time)
    #     elif self.mode == Throttle.SYNC_MODE_LB:  # if leaky bucket algo
    #         if arrival_time < (self._expected_arrival_time -
    #                            self._leaky_bucket_tolerance):  # if early
    #             # calculate wait time such that the wait will bring the
    #             # request within tolerance and not be early
    #             wait_time = (self._expected_arrival_time -
    #                          self._leaky_bucket_tolerance - arrival_time)
    #             time.sleep(wait_time)
    #      else:
    #         raise AttemptedSyncRequestInAsyncMode('The send_sync method'
    #                                               'was called for '
    #                                               'a Throttle that was '
    #                                               'instantiated with a '
    #                                               'mode of 1 for '
    #                                               'asynchronous '
    #                                               'requests.')
    #
    #     # The caller should protect the function with a try and either
    #     # raise an exception or pass back a return value that makes sense.
    #     # Putting a try around the call here and raising an exception
    #     # might not be what the caller wants.
    #     if kwargs:  # we have kwargs
    #         # if no args, then *args becomes *() which means no pos args
    #         ret_value = func(*args, **kwargs)  # make the request
    #     else:
    #         # if no args, then *args becomes *() which means no pos args
    #         ret_value = func(*args)  # make the request
    #
    #
    #     # Update the expected arrival time for the next request by
    #     # adding the request interval to our current time. Note that we
    #     # use the current time instead of the arrival time to make sure we
    #     # account for any processing delays while trying to get the
    #     # request to the service who is then observing arrival times at
    #     # its point or arrival, not ours. If we were to use our arrival
    #     # time to update the next expected arrival time, we face a
    #     # possible scenario where we send a request that gets delayed
    #     # en route to the service, but out next request arrives at the
    #     # updated expected arrival time and is sent out immediately, but it
    #     # now arrives early relative to the previous request, as observed by
    #     # the service. By using the current time, we avoid that scenario. It
    #     # does mean, however, that any built in constant delays in sending
    #     # the request will be adding an extra amount of time to our calculated
    #     # interval with the undesirable effect that all requests will now be
    #     # throttled more than they need to be.
    #     # TODO: subtract the constant path delay from the interval
    #     self._expected_arrival_time = (max(time.time(),
    #                                        self._expected_arrival_time)
    #                                    + self._interval)
    #
    #     return ret_value  # return the request return value (might be None)
    #
    # def _send_async(self,
    #                 func: Callable[[...], None],
    #                 *,
    #                 args: Optional[Tuple[Any, ...]] = (),
    #                 kwargs: Optional[Dict['str', Any]] = None
    #                 ) -> None:
    #     """Queue the request to be sent asynchronously.
    #
    #     Args:
    #         func: the request function to be run
    #         args: the request function positional arguments
    #         kwargs: the request function keyword arguments
    #
    #     """
    #     if kwargs:
    #         request_item = Throttle.Request(func, args, kwargs)
    #     else:
    #         request_item = Throttle.Request(func, args, {})
    #
    #     while not self.shutdown:
    #         try:
    #             self.request_q.put(request_item, block=True, timeout=1)
    #         except queue.Full:
    #             continue  # no need to wait since we already did
    #
    #         ###################################################################
    #         # There is a possibility that shutdown was switched to True
    #         # and the schedule_requests method saw that and cleaned up the
    #         # queue and exited BEFORE we were able to queue our request. In
    #         # that case, we need to deal with that here by simply calling
    #         # schedule_requests and run our new request from this thread.
    #         ###################################################################
    #         if not self.shutdown and not self.request_q.empty():
    #             self.schedule_requests()


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
    a_throttle = Throttle(requests=requests,
                          seconds=seconds)

    @decorator(enabled=throttle_enabled)  # type: ignore
    def wrapper(func_to_wrap: F, instance: Optional[Any],
                args: Tuple[Any, ...],
                kwargs2: Dict[str, Any]) -> Any:

        a_throttle.before_request()
        ret_value = func_to_wrap(*args, **kwargs2)
        a_throttle.after_request()

        return ret_value

    return cast(F, wrapper(wrapped))

# def throttle_queue(wrapped: Optional[F] = None, *,
#                    requests: int,
#                    seconds: Union[int, float],
#                    active_check: Callable[[], bool],
#                    throttle_enabled: Union[bool, Callable[..., bool]] = True
#                    ) -> F:
#     """Decorator to wrap a function in a throttle to avoid exceeding a limit.
#
#     The throttle wraps code around a function that is typically used to issue
#     requests to an online service. The throttle code is used to limit the
#     number of requests that are made to ensure it does not exceed a limit as
#     stated by the service. The limit is typically stated as being some number
#     of requests per some time interval. The throttle limits are spoecified via
#     the *request* and *seconds* arguments. The default is 1 request per second.
#
#     The throttle decorator can be invoked with or without arguments, and the
#     function being wrapped can optionally take arguments and optionally
#     return a value. The wrapt.decorator is used to preserve the wrapped
#     function introspection capabilities, and functools.partial is used to
#     handle the case where decorator arguments are specified. The examples
#     further below will help demonstrate the various ways in which the
#     throttle decorator can be used.
#
#     Args:
#         wrapped: Any callable function that accepts optional positional
#                    and/or optional keyword arguments, and optionally returns a
#                    value. The default is None, which will be the case when
#                    the pie decorator version is used with any of the following
#                    arguments specified.
#         requests: Number of requests that are allowed per the *seconds*
#                     specification.
#         seconds: Number of seconds in which the number of requests specified
#                    by *requests* can be made.
#         throttle_enabled: Specifies whether the start and end messages
#                             should be issued (True) or not (False). The
#                             default is True.
#
#     Returns:
#         A callable function that checks and waits if necessary to stay within
#         the limit, calls the wrapped function, saves the time of the call to
#         be used later to check the limit, and returns any return values that
#         the wrapped function returns.
#
#     :Example: statically wrapping function with throttle
#
#     >>> from scottbrian_utils.throttle import throttle
#
#     >>> _tbe = False
#
#     >>> @throttle(requests=1, seconds=1, throttle_enabled=_tbe)
#     ... def func4a() -> None:
#     ...      print('this is sample text for _tbe = False static example')
#
#     >>> func4a()  # func4a is not wrapped by throttle
#     this is sample text for _tbe = False static example
#
#     >>> _tbe = True
#
#     >>> @throttle(requests=1, seconds=1, throttle_enabled=_tbe)
#     ... def func4b() -> None:
#     ...      print('this is sample text for _tbe = True static example')
#
#     >>> func4b()  # func4b is wrapped by throttle
#     this is sample text for _tbe = True static example
#
#
#     :Example: dynamically wrapping function with throttle:
#
#     >>> from scottbrian_utils.throttle import throttle
#
#     >>> _tbe = True
#     >>> def tbe() -> bool: return _tbe
#
#     >>> @throttle(requests=1, seconds=1, throttle_enabled=tbe)
#     ... def func5() -> None:
#     ...      print('this is sample text for the tbe dynamic example')
#
#     >>> func5()  # func5 is wrapped by throttle
#     this is sample text for the tbe dynamic example
#
#
#     >>> _tbe = False
#     >>> func5()  # func5 is not wrapped by throttle
#     this is sample text for the tbe dynamic example
#
#
#     """
#     # ========================================================================
#     #  The following code covers cases where throttle is used with or without
#     #  parameters, and where the decorated function has or does not have
#     #  parameters.
#     #
#     #     Here's an example of throttle without args:
#     #         @throttle
#     #         def aFunc():
#     #             print('42')
#     #
#     #     This is what essentially happens under the covers:
#     #         def aFunc():
#     #             print('42')
#     #         aFunc = throttle(aFunc)
#     #
#     #     In fact, the above direct call can be coded as shown instead of using
#     #     the pie decorator style.
#     #
#     #     Here's an example of throttle with args:
#     #         @throttle(end='\n\n')
#     #         def aFunc():
#     #             print('42')
#     #
#     #     This is what essentially happens under the covers:
#     #         def aFunc():
#     #             print('42')
#     #         aFunc = throttle(end='\n\n')(aFunc)
#     #
#     #     Note that this is a bit more tricky: throttle(end='\n\n') portion
#     #     results in a function being returned that takes as its first
#     #     argument the separate aFunc specification in parens that we see at
#     #     the end of the first portion.
#     #
#     #     Note that we can also code the above as shown and get the same
#     #     result.
#     #
#     #     Also, we can code the following and get the same result:
#     #         def aFunc():
#     #             print('42')
#     #         aFunc = throttle(aFunc, end='\n\n')
#     #
#     #     What happens in the tricky case is throttle gets control and tests
#     #     whether aFunc was specified, and if not returns a call to
#     #     functools.partial which is the function that accepts the aFunc
#     #     specification and then calls throttle with aFunc as the first
#     #     argument with the end='\n\n' as the second argument as we now have
#     #     something that throttle can decorate.
#     #
#     #     One other complication is that we are also using the wrapt.decorator
#     #     for the inner wrapper function which does some more smoke and
#     #     mirrors to ensure introspection will work as expected.
#     # ========================================================================
#
#     if wrapped is None:
#         return cast(F, functools.partial(throttle,
#                                          requests=requests,
#                                          seconds=seconds,
#                                          active_check=active_check,
#                                          throttle_enabled=throttle_enabled))
#     a_throttle = Throttle(request_func=wrapped,
#                           requests=requests,
#                           seconds=seconds,
#                           active_check=active_check)
#
#     @decorator(enabled=throttle_enabled)  # type: ignore
#     def wrapper(func_to_wrap: F, instance: Optional[Any],
#                 args: Tuple[Any, ...],
#                 kwargs2: Dict[str, Any]) -> Any:
#
#         a_throttle.queue_request((args, kwargs2))
#
#         return
#
#     return cast(F, wrapper(wrapped))
