"""Module throttle.

========
Throttle
========

You can use the Throttle class or the @throttle decorator to limit the
number of requests made during a specific interval. Many online services
state a limit as to how many requests can be made per some time interval.
For example, "no more than one request per second", or maybe something like
"no more than 30 requests each minute". The @throttle decorator wraps a
method that makes requests to ensure that the the limit is not exceeded. The
@throttle keeps track of the time for each request and will insert a wait
(via time.sleep()) as needed to stay within the limit. Note that the
Throttle class provides the same service to allow you to use the throttle
where a decorator is not the optimal choice. Following are examples of using
both the @throttle decorator and the Throttle class methods.

:Example: use @throttle decorator for a limit of one request per second

In the example code below, in the first iteration, the @throttle
decorator code will see that there are no requests that have been made within
the last second and will allow the request to proceed. For each subsequent
call, the @throttle code will delay via time.sleep for approximately 0.9
seconds before allowing the request to proceed. This will ensure that the
limit is not exceeded.

>>> from scottbrian_utils.throttle import Throttle
>>> import time
>>> @throttle(requests=1, seconds=1, mode=Throttle.MODE_SYNC)
>>> def make_request():
...     time.sleep(.1)  # simulate request that takes 1/10 second
>>> for i in range(100):
...     make_request()


:Example: use Throttle methods for a limit of one request per second

In the example code below, each call to send_request passes the request
funtion and its args. For the first iteration, send_request will see that
there are no requests that have been made within the last second and will
call the request function without delay. For each subsequent call,
send_request will delay via time.sleep for approximately 0.9
seconds before allowing the request to proceed. This will ensure that the
limit is not exceeded.

>>> from scottbrian_utils.throttle import Throttle
>>> import time
>>> def my_request(idx, *, life):
...     print(f'my_request entered with idx {idx}, and life is {life}')
>>> request_throttle = Throttle(requests=1, seconds=1, mode=Throttle.MODE_SYNC)
>>> for i in range(3):
...     request_throttle.send_request(my_req, i, life='good')
my_request entered with idx 1, and life is good
my_request entered with idx 1, and life is good
my_request entered with idx 1, and life is good

Example: use @throttle decorator for a limit of 20 requests per minute with the
         early count algorithm

In this example, we are allowing up to 20 requests per minute. In this case
the @throttle decorator code will allow the first 20 requests to go through
without waiting. When the 21st request is made, the @throttle code will wait to
ensure we remain within the limit. More specifically, with each request being
made approximately every .1 seconds, the first 20 request took approximately 2
seconds. Thus, @throttle code will wait for 58 seconds before allowing the
21st request to proceed.

>>> from scottbrian_utils.throttle import Throttle
>>> import time
>>> @throttle(requests=20, seconds=60, mode=Throttle.MODE_SYNC_EC,
...           early_count=20)
>>> def make_request():
...     time.sleep(.1)  # simulate request that takes 1/10 second
>>> for i in range(21):
...     make_request()


As can be seen with the above example, we were able to allow a burst of
20 requests and still remain within the limit (i.e., if the service in
stating no more thna 20 requests per minutes is OK with getting a burst of
20 each minute). Uing mode Throttle.MODE_ASYNC or Throttle.MODE_SYNC without
the early count algorithm will simply delay the requests by a uniform 3
seconds each to ensure we remain with the 60 second limit for 20 requests.

The throttle module contains:

    1) Throttle class with methods:

       a. send_request
       b. start_shutdown
    2) Error exception classes:

       a. IncorrectNumberRequestsSpecified
       b. IncorrectPerSecondsSpecified
    3) @throttle decorator

"""
import time
import threading
import queue
import inspect

from datetime import timedelta
from typing import (Any, Callable, cast, Dict, Final, NamedTuple, Optional,
                    Tuple, Type, TYPE_CHECKING, TypeVar, Union)
import functools
from wrapt.decorators import decorator  # type: ignore
from scottbrian_utils.diag_msg import diag_msg

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


class IncorrectAsyncQSizeSpecified(ThrottleError):
    """Throttle exception for an incorrect async_q_size specification."""
    pass


class AsyncQSizeNotAllowed(ThrottleError):
    """Throttle exception for async_q_size specified when not allowed."""
    pass


class IncorrectEarlyCountSpecified(ThrottleError):
    """Throttle exception for an incorrect early_count specification."""
    pass


class MissingEarlyCountSpecification(ThrottleError):
    """Throttle exception for missing early_count specification."""
    pass


class EarlyCountNotAllowed(ThrottleError):
    """Throttle exception for early_count specified when not allowed."""
    pass


class IncorrectLbThresholdSpecified(ThrottleError):
    """Throttle exception for an incorrect lb_threshold specification."""
    pass


class MissingLbThresholdSpecification(ThrottleError):
    """Throttle exception for missing lb_threshold specification."""
    pass


class LbThresholdNotAllowed(ThrottleError):
    """Throttle exception for lb_threshold specified when not allowed."""
    pass


class IncorrectStartShutdownEventSpecified(ThrottleError):
    """Throttle exception for incorrect start_shutdown_event specification."""
    pass


class StartShutdownEventNotAllowed(ThrottleError):
    """Throttle exception start_shutdown_event specified when not allowed."""
    pass


class MissingStartShutdownEvent(ThrottleError):
    """Throttle exception for missing start_shutdown_event."""
    pass


class IncorrectShutdownCompleteEventSpecified(ThrottleError):
    """Throttle exception incorrect shutdown_complete_event specification."""
    pass


class ShutdownCompleteEventNotAllowed(ThrottleError):
    """Throttle exception shutdown_complete_event specified not allowed."""
    pass


class MissingShutdownCompleteEvent(ThrottleError):
    """Throttle exception for missing shutdown_complete_event."""
    pass


class AttemptedShutdownForSyncThrottle(ThrottleError):
    """Throttle exception for shutdown not in mode Throttle.MODE_ASYNC."""
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

    MODE_ASYNC: Final[int] = 1
    MODE_SYNC: Final[int] = 2
    MODE_SYNC_EC: Final[int] = 3
    MODE_SYNC_LB: Final[int] = 4
    MODE_MAX: Final[int] = MODE_SYNC_LB

    DEFAULT_ASYNC_Q_SIZE: Final[int] = 4096

    def __init__(self, *,
                 requests: int,
                 seconds: Union[int, float],
                 mode: int,
                 async_q_size: Optional[int] = None,
                 early_count: Optional[int] = None,
                 lb_threshold: Optional[Union[int, float]] = None,
                 start_shutdown_event: Optional[threading.Event] = None,
                 shutdown_complete_event: Optional[threading.Event] = None
                 ) -> None:
        """Initialize an instance of the Throttle class.

        Args:
            requests: The number of requests that can be made in
                        the interval specified by seconds.
            seconds: The number of seconds in which the number of requests
                       specified in requests can be made.
            mode: Specifies one of four modes for the throttle.

                  1) mode=Throttle.MODE_ASYNC specifies asynchronous mode.
                     With asynchoneous throttling,
                     each request is placed on a queue and control returns
                     to the caller. A separate thread then executes each
                     request at a steady interval to acheieve the specified
                     number of requests per the specified number of seconds.
                     Since the caller is given back control, any return
                     values from the request must be handled by an
                     established protocol between the caller and the request,
                     (e.g., a callback method).
                  2) mode=Throttle.MODE_SYNC specifies synchonous mode.
                     For synchronous throttling, the caller may be blocked to
                     delay the request in order to achieve the the specified
                     number of requests per the specified number of seconds.
                     Since the request is handled synchronously on the same
                     thread, any return value from the request will be
                     immediately returned to the caller when the request
                     completes.
                  3) mode=Throttle.MODE_SYNC_EC specifies synchronous mode
                     using an early arrival algorithm.
                     For synchronous throttleing with the early
                     arrival algorithm, some number of requests are sent
                     immediatly without delay even though they may have
                     arrived at a quicker pace than that allowed by the
                     the requests and seconds specification. An early_count
                     specification is required when mode Throttle.MODE_SYNC_EC
                     is specified. See the early_count parameter for details.
                  4) mode=Throttle.MODE_SYNC_LB specifies synchronous mode
                     using a leaky bucket algorithm.
                     For synchronous throttleing with the leaky bucket
                     algorithm, some number of requests are sent
                     immediatly without delay even though they may have
                     arrived at a quicker pace than that allowed by the
                     the requests and seconds specification. A
                     lb_threshold specification is required when mode
                     Throttle.MODE_SYNC_LB is specified. See the
                     lb_threshold parameter for details.
            async_q_size: Specifies the size of the request
                            queue for async requests. When the request
                            queue is totaly populated, any additional
                            calls to send_request will be delayed
                            until queued requests are removed and
                            scheduled. The default is 4096 requests.
            early_count: Specifies the number of requests that are allowed
                           to proceed that arrive earlier than the
                           allowed interval. The count of early requests
                           is incremented, and when it exceeds the
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
                            Throttle.MODE_SYNC_LB is specified for mode.
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
            start_shutdown_event: An event that the client will post when
                                    shutdown is to be started. See the
                                    description further down regarding the
                                    throttle states to understand what
                                    shutdown processing does.
                                    Required and valid only for the
                                    throttle decorator with mode
                                    Throttle.MODE_ASYNC.
            shutdown_complete_event: An event that the client will wait
                                       upon to be posted once shutdown is
                                       complete. See the description further
                                       down regarding the throttle states to
                                       understand what shutdown processing
                                       does. Required and valid only for
                                       the throttle decorator with mode
                                       Throttle.MODE_ASYNC.

        Raises:
            IncorrectRequestsSpecified: The requests specification must be
                                          a positive integer greater than
                                          zero.
            IncorrectSecondsSpecified: The seconds specification must be
                                         a positive int or float greater
                                         than zero.
            IncorrectModeSpecified: The mode specification must be an
                                      integer with a value of 1, 2, 3, or 4.
                                      Use Throttle.MODE_ASYNC,
                                      Throttle.MODE_SYNC,
                                      Throttle.MODE_SYNC_EC, or
                                      Throttle.MODE_SYNC_LB.
            AsyncQSizeNotAllowed: async_q_size is valid for mode
                                    Throttle.MODE_ASYNC only.
            IncorrectAsyncQSizeSpecified: async_q_size must be an integer
                                            greater than zero.
            EarlyCountNotAllowed: early_count is valid and required for mode
                                    Throttle.MODE_SYNC_EC only.
            IncorrectEarlyCountSpecified: early_count must be an integer
                                            greater than zero.
            MissingEarlyCountSpecification: early_count is required for mode
                                              Throttle.MODE_SYNC_EC.
            LbThresholdNotAllowed: lb_threshold is valid and required for
                                     mode Throttle.MODE_SYNC_LB only.
            IncorrectLbThresholdSpecified: lb_threshold must be an integer or
                                             float greater than zero.
            MissingLbThresholdSpecification: lb_threshold is required for
                                               mode Throttle.MODE_SYNC_LB.
            StartShutdownEventNotAllowed: start_shutdown_event is valid only
                                            for the throttle decorator with
                                            mode Throttle.MODE_ASYNC.
            IncorrectStartShutdownEventSpecified: start_shutdown_event must
                                                    be a threading Event
                                                    object
            MissingStartShutdownEvent: A start_shutdown_event is required for
                                         the decorator with mode
                                         Throttle.MODE_ASYNC.
            ShutdownCompleteEventNotAllowed: shutdown_complete_event is
                                               valid only for the throttle
                                               decorator with mode
                                               Throttle.MODE_ASYNC
            IncorrectShutdownCompleteEventSpecified: shutdown_complete_event
                                               must be a threading Event
                                               object.
            MissingShutdownCompleteEvent: A shutdown_complete_event is
                                            required for the decorator with
                                            mode Throttle.MODE_ASYNC.

        States and processing for mode Throttle.MODE_ASYNC:

            The Throttle is initialized with an empty async_q and the
            scheduler thread is started and ready to receive work. The
            starting state is 'active'.

            1) state: active
               a) send_request called (directly or via decorated func call):
                  1) request is queued to the async_q
                  2) state remains 'active'
               b) start_shutdown called (non-decorator only):
                  1) state is changed to 'shutdown'
                  2) scheduler removes but does not schedule async_q items
                  3) scheduler exits
                  4) control returns after scheduler thread returns
               c) start_shutdown_event is set (decorator only):
                  1) state is changed to 'shutdown'
                  2) scheduler removes but does not schedule async_q items
                  3) scheduler exits
                  4) shutdown_complete_event is set
            2) state: shutdown
               a) send_request called (directly or via decorated func call):
                  1) request is ignored  (i.e, not queued to async_q)
               b) start_shutdown called (non-decorator only):
                  1) state remains 'shutdown'
                  2) control returns immediately
               c) start_shutdown_event is set (decorator only):
                  1) state remains 'shutdown'
                  2) shutddown_complete_event set


        :Example: instantiate an async throttle for 1 request per second

        >>> from scottbrian_utils.throttle import Throttle
        >>> request_throttle = Throttle(requests=1,
        ...                             seconds=1,
        ...                             mode=Throttle.MODE_ASYNC)


        :Example: instantiate an async throttle for 5 requests per 1/2 second
                  with an async queue size of 256

        >>> from scottbrian_utils.throttle import Throttle
        >>> from threading import Event
        >>> request_throttle = Throttle(requests=5,
        ...                             seconds=0.5,
        ...                             mode=Throttle.MODE_ASYNC,
        ...                             async_q_size=256)


        :Example: instantiate a throttle for 20 requests per 2 minutes using
                  the early count algorithm

        >>> from scottbrian_utils.throttle import Throttle
        >>> request_throttle = Throttle(requests=5,
        ...                             seconds=120,
        ...                             mode=Throttle.MODE_SYNC_EC,
        ...                             early_count=3)


        :Example: instantiate a throttle for 3 requests per second
                  using the leaky bucket algorithm

        >>> from scottbrian_utils.throttle import Throttle
        >>> request_throttle = Throttle(requests=5,
        ...                             seconds=120,
        ...                             mode=Throttle.MODE_SYNC_LB,
        ...                             lb_threshold=5)


        """
        #######################################################################
        # determine whether we are throttle decorator
        #######################################################################
        if inspect.currentframe().f_back.f_code.co_name == 'throttle':
            self.decorator = True
        else:
            self.decorator = False

        #######################################################################
        # requests
        #######################################################################
        if (isinstance(requests, int)
                and (0 < requests)):
            self.requests = requests
        else:
            raise IncorrectRequestsSpecified('The requests '
                                             'specification must be a '
                                             'positive integer greater '
                                             'than zero.')

        #######################################################################
        # seconds
        #######################################################################
        if isinstance(seconds, (int, float)) and (0 < seconds):
            self.seconds = timedelta(seconds=seconds)
        else:
            raise IncorrectSecondsSpecified('The seconds specification '
                                            'must be an integer or '
                                            'float greater than zero.')

        #######################################################################
        # mode
        #######################################################################
        if (isinstance(mode, int)
                and mode in (Throttle.MODE_ASYNC, Throttle.MODE_SYNC,
                             Throttle.MODE_SYNC_LB, Throttle.MODE_SYNC_EC)):
            self.mode = mode
        else:
            raise IncorrectModeSpecified('The mode specification must be an '
                                         'integer with value 1, 2, 3, or 4.')

        #######################################################################
        # async_q_size
        #######################################################################
        if async_q_size is not None:
            if mode != Throttle.MODE_ASYNC:
                raise AsyncQSizeNotAllowed('async_q_size is valid '
                                           'for mode Throttle.MODE_ASYNC '
                                           'only.')
            else:
                if (isinstance(async_q_size, int) and
                        (0 < async_q_size)):
                    self.async_q_size = async_q_size
                else:
                    raise IncorrectAsyncQSizeSpecified('async_q_size '
                                                       'must be an '
                                                       'integer greater'
                                                       'than zero.')
        else:
            self.async_q_size = Throttle.DEFAULT_ASYNC_Q_SIZE

        #######################################################################
        # early_count
        #######################################################################
        if early_count is not None:
            if mode != Throttle.MODE_SYNC_EC:
                raise EarlyCountNotAllowed('early_count is valid and required '
                                           'for mode Throttle.MODE_SYNC_EC '
                                           'only.')

            else:
                if isinstance(early_count, int) and (0 < early_count):
                    self.early_count = early_count
                else:
                    raise IncorrectEarlyCountSpecified('early_count must be '
                                                       'an integer greater'
                                                       'than zero.')
        else:
            if mode == Throttle.MODE_SYNC_EC:
                raise MissingEarlyCountSpecification('early_count is '
                                                     'required for mode '
                                                     'Throttle.MODE_SYNC_EC.')
            else:
                self.early_count = 0

        #######################################################################
        # lb_threshold
        #######################################################################
        if lb_threshold is not None:
            if mode != Throttle.MODE_SYNC_LB:
                raise LbThresholdNotAllowed('lb_threshold is valid and '
                                            'required for mode '
                                            'Throttle.MODE_SYNC_LB only.')
            else:
                if (isinstance(lb_threshold, (int, float))
                        and (0 < lb_threshold)):
                    self.lb_threshold = float(lb_threshold)
                else:
                    raise IncorrectLbThresholdSpecified('lb_threshold must be '
                                                        'an integer or '
                                                        'float greater than '
                                                        'zero.')
        else:
            if mode == Throttle.MODE_SYNC_LB:
                raise MissingLbThresholdSpecification('lb_threshold is '
                                                      'required for mode '
                                                      'Throttle.MODE_SYNC_LB.')
            else:
                self.lb_threshold = 0

        #######################################################################
        # start_shutdown_event
        #######################################################################
        if start_shutdown_event is not None:
            if (mode != Throttle.MODE_ASYNC) or (not self.decorator):
                raise StartShutdownEventNotAllowed(
                    'start_shutdown_event is valid only for the throttle '
                    'decorator with mode Throttle.MODE_ASYNC.')
            else:
                if isinstance(start_shutdown_event, threading.Event):
                    self.start_shutdown_event = start_shutdown_event
                else:
                    raise IncorrectStartShutdownEventSpecified(
                        'start_shutdown_event must be a threading Event '
                        'object.')
        else:
            self.start_shutdown_event = None
            if self.decorator and (mode == Throttle.MODE_ASYNC):
                raise MissingStartShutdownEvent(
                    'A start_shutdown_event is required for the decorator '
                    'with mode Throttle.MODE_ASYNC.')

        #######################################################################
        # shutdown_complete_event
        #######################################################################
        if shutdown_complete_event is not None:
            if (mode != Throttle.MODE_ASYNC) or (not self.decorator):
                raise ShutdownCompleteEventNotAllowed(
                    'shutdown_complete_event is valid only for the throttle '
                    'decorator with mode Throttle.MODE_ASYNC.')
            else:
                if isinstance(shutdown_complete_event, threading.Event):
                    self.shutdown_complete_event = shutdown_complete_event
                else:
                    raise IncorrectShutdownCompleteEventSpecified(
                        'shutdown_complete_event must be a threading Event '
                        'object.')
        else:
            self.shutdown_complete_event = None
            if self.decorator and (mode == Throttle.MODE_ASYNC):
                raise MissingShutdownCompleteEvent(
                    'A shutdown_complete_event is required for the decorator '
                    'with mode Throttle.MODE_ASYNC.')

        #######################################################################
        # Set remainder of vars
        #######################################################################
        self.target_interval = seconds/requests
        self.schedule_lock = threading.Lock()
        self._shutdown = False
        self._expected_arrival_time = 0
        self._early_arrival_count = 0

        if mode == Throttle.MODE_ASYNC:
            self.async_q = queue.Queue(maxsize=self.async_q_size)
            self.request_scheduler_thread = threading.Thread(
                    target=self.schedule_requests)
            self.request_scheduler_thread.start()
        else:
            self.async_q = None
            self.request_scheduler_thread = None

    ###########################################################################
    # len
    ###########################################################################
    def __len__(self) -> int:
        """Return the number of items in the async_q.

        Returns:
            The number of entries in the async_q as an integer

        The calls to the send_request add request items to the async_q
        for mode Throttle.MODE_ASYNC. The request items are
        eventually removed and scheduled. The len of Throttle is the
        number of request items on the async_q when the len function
        is called. Note that the returned queue size is the approximate
        size as described in the documentation for the python threading
        queue.

        :Example: instantiate a throttle for 1 request per second

        >>> from scottbrian_utils.throttle import Throttle
        >>> import time
        >>> def my_request(idx):
        ...     print('idx:' idx)
        >>> request_throttle = Throttle(requests=1,
        ...                             seconds=1,
        ...                             mode=Throttle.MODE_ASYNC)
        >>> for i in range(3):  # quickly send 3 items (2 get queued)
        ...     request_throttle.send_request(my_request,i)
        >>> print(len(request_throttle))
        idx: 0
        6
        idx: 1
        idx: 2

        """
        if self.mode == Throttle.MODE_ASYNC:
            return self.async_q.qsize()
        else:
            return 0

    ###########################################################################
    # repr
    ###########################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example: instantiate a throttle for 20 requests per 1/2 minute

         >>> from scottbrian_utils.throttle import Throttle
        >>> request_throttle = Throttle(requests=30,
        ...                             seconds=30,
        ...                             mode=Throttle.MODE_ASYNC)
        >>> repr(request_throttle)
        Throttle(requests=20, seconds=30, mode=Throttle.MODE_ASYNC)

        """
        if TYPE_CHECKING:
            __class__: Type[Throttle]
        classname = self.__class__.__name__
        parms = f'requests={self.requests}, ' \
                f'seconds={self.seconds.total_seconds()}, '

        if self.mode == Throttle.MODE_ASYNC:
            parms += f'mode=Throttle.MODE_ASYNC, ' \
                     f'async_q_size={self.async_q_size}'
            # Client specified event are only valid with the throttle
            # decorator.
            # if self.start_shutdown_event:
            #     parms += f', start_shutdown_event=' \
            #              f'start_shutdown_event'
            # if self.shutdown_complete_event:
            #     parms += f', shutdown_complete_event=' \
            #              f'shutdown_complete_event'
        elif self.mode == Throttle.MODE_SYNC:
            parms += f'mode=Throttle.MODE_SYNC'
        elif self.mode == Throttle.MODE_SYNC_EC:
            parms += f'mode=Throttle.MODE_SYNC_EC, ' \
                     f'early_count={self.early_count}'
        else:
            parms += f'mode=Throttle.MODE_SYNC_LB, ' \
                     f'lb_threshold={self.lb_threshold}'

        return f'{classname}({parms})'

    ###########################################################################
    # shutdown check
    ###########################################################################
    @property
    def shutdown(self) -> bool:
        """Determine whether we need to shutdown.

        Returns:
            True if we need to start shutdown processing, False otherwise
        """
        # If client provided a start_shutdown_event and it is set,
        # set self._shutdown to True.
        if self.start_shutdown_event and self.start_shutdown_event.is_set():
            self._shutdown = True
        return self._shutdown

    ###########################################################################
    # start_shutdown
    ###########################################################################
    def start_shutdown(self) -> None:
        """Shutdown the throttle request scheduling.

        Raises:
            AttemptedShutdownForSyncThrottle: Calling start_shutdown is only
                                                valid for a throttle
                                                instantiated with a mode of
                                                Throttle.MODE_ASYNC                                             shutthe shutdown
        """
        if self.mode == Throttle.MODE_ASYNC:
            self._shutdown = True  # indicate shutdown in progress
            self.request_scheduler_thread.join()  # wait for cleanup
        else:
            raise AttemptedShutdownForSyncThrottle('Calling start_shutdown is '
                                                   'valid only for a throttle '
                                                   'instantiated with mode '
                                                   'Throttle.MODE_ASYNC.')

    ###########################################################################
    # send_request
    ###########################################################################
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
        if self.mode == Throttle.MODE_ASYNC:
            request_item = Throttle.Request(func, args, kwargs)
            while not self._shutdown:
                try:
                    self.async_q.put(request_item,
                                     block=True,
                                     timeout=0.5)
                    break
                except queue.Full:
                    continue  # no need to wait since we already did

            # There is a possibility that the following steps occur in
            # the following order:
            # 1) send_request is entered for async mode and sees at
            # the while statement that we are *not* in shutdown
            # 2) send_request proceeds to the try statement just before
            # the request will be queued to the async_q
            # 2) shutdown is requested and is detected by
            # schedule_requests
            # 3) schedule_requests cleans up the async_q end exits
            # 4) back in send_request, we put our request on the
            # async_q
            # The following section of code handles that case and cleans
            # up the async_q of anything added after the scheduler has
            # exited
            if self._shutdown:
                while not self.async_q.empty():
                    _ = self.async_q.get()

        #######################################################################
        # SYNC_MODE
        #######################################################################
        else:
            arrival_time = time.time()  # time that this request is being made

            ###################################################################
            # The Throttle class can be instantiated for sync, sync with the
            # early count algo, or sync with the leaky bucket algo. For
            # straight sync and sync with leaky bucket, the
            # _early_arrival_count will have no effect. For straight sync and
            # sync with early count, the _leaky_bucket_tolerance will be zero.
            ###################################################################
            if arrival_time < self._expected_arrival_time:
                self._early_arrival_count += 1
                if ((self.mode != Throttle.MODE_SYNC_EC) or
                        (self.early_count <
                            self._early_arrival_count)):
                    self._early_arrival_count = 0  # reset the count
                    wait_time = self._expected_arrival_time - arrival_time
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
            # its point of arrival, not ours. If we were to use our arrival
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
                                               self._expected_arrival_time
                                               + self.lb_threshold
                                               )
                                           - self.lb_threshold
                                           + self.target_interval)

            return ret_value  # return the request return value (might be None)

    ###########################################################################
    # schedule_requests
    ###########################################################################
    def schedule_requests(self) -> None:
        """Get tasks from queue and run them."""
        # Requests will be scheduled from the async_q at the interval
        # calculated from the requests and seconds arguments when the
        # throttle is instantiated. If shutdown is indicated,
        # the async_q will be cleaned up with any remaining requests
        # dropped. Note that async_q.get will only wait for a second so
        # we can detect shutdown in a timely fashion.
        while not self.shutdown:
            try:
                request_item = self.async_q.get(block=True, timeout=1)
            except queue.Empty:
                continue  # no need to wait since we already did
            ###################################################################
            # Call the request function.
            # We use try/except to ignore any unhandled errors so we can
            # keep going.
            ###################################################################
            try:
                request_item.request_func(*request_item.args,
                                          **request_item.kwargs)
            except Exception:
                pass

            ###############################################################
            # wait (i.e., throttle)
            # Note that the wait time could be anywhere from a fraction of
            # a second to several seconds. We want to be responsive in
            # case we need to bail for shutdown, so we wait in 1 second
            # or less increments and bail if we detect shutdown.
            ###############################################################
            wait_seconds = self.target_interval  # could be small or large
            while wait_seconds > 0 and not self.shutdown:
                time.sleep(min(1, wait_seconds))
                wait_seconds = wait_seconds - 1

        # if we are here, shutdown was detected
        while not self.async_q.empty():
            _ = self.async_q.get()
        if self.shutdown_complete_event:
            self.shutdown_complete_event.set()


###############################################################################
# Pie Throttle Decorator
###############################################################################
F = TypeVar('F', bound=Callable[..., Any])


def throttle(wrapped: Optional[F] = None, *,
             requests: int,
             seconds: Union[int, float],
             mode: int,
             async_q_size: Optional[int] = None,
             early_count: Optional[int] = None,
             lb_threshold: Optional[Union[int, float]] = None,
             start_shutdown_event: Optional[threading.Event] = None,
             shutdown_complete_event: Optional[threading.Event] = None
             ) -> F:
    """Decorator to wrap a function in a throttle to avoid exceeding a limit.

    The throttle wraps code around a function that is typically used to issue
    requests to an online service. Some services state a limit as to how
    many requests can be made per some time interval (e.g., 3 requests per
    second). The throttle code ensures that the limit is not exceeded.

    Args:
        wrapped: Any callable function that accepts optional positional
                   and/or optional keyword arguments, and optionally returns a
                   value. The default is None, which will be the case when
                   the pie decorator version is used with any of the following
                   arguments specified.
        requests: The number of requests that can be made in
                    the interval specified by seconds.
        seconds: The number of seconds in which the number of requests
                   specified in requests can be made.
        mode: Specifies one of four modes for the throttle.

              1) mode=Throttle.MODE_ASYNC specifies asynchronous mode.
                 With asynchoneous throttling,
                 each request is placed on a queue and control returns
                 to the caller. A separate thread then executes each
                 request at a steady interval to acheieve the specified
                 number of requests per the specified number of seconds.
                 Since the caller is given back control, any return
                 values from the request must be handled by an
                 established protocol between the caller and the request,
                 (e.g., a callback method).
              2) mode=Throttle.MODE_SYNC specifies synchonous mode.
                 For synchronous throttling, the caller may be blocked to
                 delay the request in order to achieve the the specified
                 number of requests per the specified number of seconds.
                 Since the request is handled synchronously on the same
                 thread, any return value from the request will be
                 immediately returned to the caller when the request
                 completes.
              3) mode=Throttle.MODE_SYNC_EC specifies synchronous mode
                 using an early arrival algorithm.
                 For synchronous throttleing with the early
                 arrival algorithm, some number of requests are sent
                 immediatly without delay even though they may have
                 arrived at a quicker pace than that allowed by the
                 the requests and seconds specification. An early_count
                 specification is required when mode Throttle.MODE_SYNC_EC
                 is specified. See the early_count parameter for details.
              4) mode=Throttle.MODE_SYNC_LB specifies synchronous mode
                 using a leaky bucket algorithm.
                 For synchronous throttleing with the leaky bucket
                 algorithm, some number of requests are sent
                 immediatly without delay even though they may have
                 arrived at a quicker pace than that allowed by the
                 the requests and seconds specification. A
                 lb_threshold specification is required when mode
                 Throttle.MODE_SYNC_LB is specified. See the
                 lb_threshold parameter for details.
        async_q_size: Specifies the size of the request
                        queue for async requests. When the request
                        queue is totaly populated, any additional
                        calls to send_request will be delayed
                        until queued requests are removed and
                        scheduled. The default is 4096 requests.
        early_count: Specifies the number of requests that are allowed
                       to proceed that arrive earlier than the
                       allowed interval. The count of early requests
                       is incremented, and when it exceeds the
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
                        Throttle.MODE_SYNC_LB is specified for mode.
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
        start_shutdown_event: An event that the client will post when
                                shutdown is to be started. See the
                                description further down regarding the
                                throttle states to understand what
                                shutdown processing does.
                                Required and valid only for the
                                throttle decorator with mode
                                Throttle.MODE_ASYNC.
        shutdown_complete_event: An event that the client will wait
                                   upon to be posted once shutdown is
                                   complete. See the description further
                                   down regarding the throttle states to
                                   understand what shutdown processing
                                   does. Required and valid only for
                                   the throttle decorator with mode
                                   Throttle.MODE_ASYNC.

    Raises:
        IncorrectRequestsSpecified: The requests specification must be
                                      a positive integer greater than
                                      zero.
        IncorrectSecondsSpecified: The seconds specification must be
                                     a positive int or float greater
                                     than zero.
        IncorrectModeSpecified: The mode specification must be an
                                  integer with a value of 1, 2, 3, or 4.
                                  Use Throttle.MODE_ASYNC,
                                  Throttle.MODE_SYNC,
                                  Throttle.MODE_SYNC_EC, or
                                  Throttle.MODE_SYNC_LB.
        AsyncQSizeNotAllowed: async_q_size is valid for mode
                                Throttle.MODE_ASYNC only.
        IncorrectAsyncQSizeSpecified: async_q_size must be an integer
                                        greater than zero.
        EarlyCountNotAllowed: early_count is valid and required for mode
                                Throttle.MODE_SYNC_EC only.
        IncorrectEarlyCountSpecified: early_count must be an integer
                                        greater than zero.
        MissingEarlyCountSpecification: early_count is required for mode
                                          Throttle.MODE_SYNC_EC.
        LbThresholdNotAllowed: lb_threshold is valid and required for
                                 mode Throttle.MODE_SYNC_LB only.
        IncorrectLbThresholdSpecified: lb_threshold must be an integer or
                                         float greater than zero.
        MissingLbThresholdSpecification: lb_threshold is required for
                                           mode Throttle.MODE_SYNC_LB.
        StartShutdownEventNotAllowed: start_shutdown_event is valid only
                                        for the throttle decorator with
                                        mode Throttle.MODE_ASYNC.
        IncorrectStartShutdownEventSpecified: start_shutdown_event must
                                                be a threading Event
                                                object
        MissingStartShutdownEvent: A start_shutdown_event is required for
                                     the decorator with mode
                                     Throttle.MODE_ASYNC.
        ShutdownCompleteEventNotAllowed: shutdown_complete_event is
                                           valid only for the throttle
                                           decorator with mode
                                           Throttle.MODE_ASYNC
        IncorrectShutdownCompleteEventSpecified: shutdown_complete_event
                                           must be a threading Event
                                           object.
        MissingShutdownCompleteEvent: A shutdown_complete_event is
                                        required for the decorator with
                                        mode Throttle.MODE_ASYNC.


    Returns:
        A callable function that, for mode Throttle.MODE_ASYNC, queues the
        request to be scheduled in accordance with the specified limits, or,
        for all other modes, delays the request as needed in accordance with
        the specified limits.

    States and processing for mode Throttle.MODE_ASYNC:

        The Throttle is initialized with an empty async_q and the
        scheduler thread is started and ready to receive work. The
        starting state is 'active'.

        1) state: active
           a) send_request called (directly or via decorated func call):
              1) request is queued to the async_q
              2) state remains 'active'
           b) start_shutdown called (non-decorator only):
              1) state is changed to 'shutdown'
              2) scheduler removes but does not schedule async_q items
              3) scheduler exits
              4) control returns after scheduler thread returns
           c) start_shutdown_event is set (decorator only):
              1) state is changed to 'shutdown'
              2) scheduler removes but does not schedule async_q items
              3) scheduler exits
              4) shutdown_complete_event is set
        2) state: shutdown
           a) send_request called (directly or via decorated func call):
              1) request is ignored  (i.e, not queued to async_q)
           b) start_shutdown called (non-decorator only):
              1) state remains 'shutdown'
              2) control returns immediately
           c) start_shutdown_event is set (decorator only):
              1) state remains 'shutdown'
              2) shutddown_complete_event set


        :Example: wrap a function with an async throttle for 1 request per
                  second

        >>> from scottbrian_utils.throttle import Throttle
        >>> @throttle(requests=1, seconds=1, mode=Throttle.MODE_ASYNC)
        ... def f1() -> None:
        ...     print('example 1 request function')


        :Example: Instantiate an async throttle for 5 requests per 1/2 second
                  with an async queue size of 256 and an event to start a
                  shutdown when set, and an event to wait upon for shutdown
                  to complete.

        >>> from scottbrian_utils.throttle import Throttle
        >>> from threading import Event
        >>> start_shutdown = Event()
        >>> shutdown_done = Event()
        >>> request_throttle = Throttle(requests=5,
        ...                             seconds=0.5,
        ...                             mode=Throttle.MODE_ASYNC,
        ...                             async_q_size=256,
        ...                             start_shutdown_event=start_shutdown,
        ...                             shutdown_complete_event=shutdown_done)

        :Example: wrap a function with an async throttle for 5 requests
                  per 1/2 second with an async queue size of 256 and an event
                  to start a shutdown when set, and an event to wait upon
                  for shutdown to complete.

        >>> from scottbrian_utils.throttle import Throttle
        >>> from threading import Event
        >>> start_shutdown = Event()
        >>> shutdown_done = Event()
        >>> @throttle(requests=5,
        ...           seconds=0.5,
        ...           mode=Throttle.MODE_ASYNC,
        ...           async_q_size=256,
        ...           start_shutdown_event=start_shutdown,
        ...           shutdown_complete_event=shutdown_done)
        ... def f2(a) -> None:
        ...     print(f'example 2 request function with arg {a}')


        :Example: wrap a function with a throttle for 20 requests per 2 minutes
                  using the early count algo

        >>> from scottbrian_utils.throttle import Throttle
        >>> @throttle(requests=5,
        ...           seconds=120,
        ...           mode=Throttle.MODE_SYNC_EC,
        ...           early_count=3)
        ... def f3(b=3) -> int:
        ...     print(f'example 3 request function with arg {b}')
        ...     return b * 5


        :Example: wrap a function with a throttle for 3 requests per second
                  using the leaky bucket algo

        >>> from scottbrian_utils.throttle import Throttle
        >>> @throttle(requests=5,
        ...           seconds=120,
        ...           mode=Throttle.MODE_SYNC_LB,
        ...           lb_threshold=5)
        ... def f4(a, *, b=4) -> int:
        ...     print(f'example 4 request function with args {a} and {b}')
        ...     return b * 7


        """
    # ========================================================================
    #  The following code covers cases where throttle is used with or without
    #  the pie character, where the decorated function has or does not have
    #  parameters.
    #
    #     Here's an example of throttle with a function that has no args:
    #         @throttle(requests=1, seconds=1, mode=Throttle.MODE_SYNC)
    #         def aFunc():
    #             print('42')
    #
    #     This is what essentially happens under the covers:
    #         def aFunc():
    #             print('42')
    #         aFunc = throttle(requests=1,
    #                          seconds=1,
    #                          mode=Throttle.MODE_SYNC)(aFunc)
    #
    #     The call to throttle results in a function being returned that takes
    #     as its first argument the aFunc specification that we see in parens
    #     immediately following the throttle call.
    #
    #     Note that we can also code the above as shown and get the same
    #     result.
    #
    #     Also, we can code the following and get the same result:
    #         def aFunc():
    #             print('42')
    #         aFunc = throttle(aFunc,
    #                          requests=1,
    #                          seconds=1,
    #                          mode=Throttle.MODE_SYNC)
    #
    #     What happens is throttle gets control and tests whether aFunc
    #     was specified, and if not returns a call to functools.partial
    #     which is the function that accepts the aFunc
    #     specification and then calls throttle with aFunc as the first
    #     argument with the other args for requests, seconds, and mode).
    #
    #     One other complication is that we are also using the wrapt.decorator
    #     for the inner wrapper function which does some more smoke and
    #     mirrors to ensure introspection will work as expected.
    # ========================================================================

    if wrapped is None:
        return cast(F, functools.partial(throttle,
                                         requests=requests,
                                         seconds=seconds,
                                         mode=mode,
                                         async_q_size=async_q_size,
                                         early_count=early_count,
                                         lb_threshold=lb_threshold,
                                         start_shutdown_event=
                                         start_shutdown_event,
                                         shutdown_complete_event=
                                         shutdown_complete_event))
    a_throttle = Throttle(requests=requests,
                          seconds=seconds,
                          mode=mode,
                          async_q_size=async_q_size,
                          early_count=early_count,
                          lb_threshold=lb_threshold,
                          start_shutdown_event=start_shutdown_event,
                          shutdown_complete_event=shutdown_complete_event)

    @decorator  # type: ignore
    def wrapper(func_to_wrap: F, instance: Optional[Any],
                args: Tuple[Any, ...],
                kwargs2: Dict[str, Any]) -> Any:

        ret_value = a_throttle.send_request(func_to_wrap, *args, **kwargs2)
        return ret_value

    return cast(F, wrapper(wrapped))
