"""Module smart_event.

=============
SmartEvent
=============

You can use the SmartEvent class to coordinate activities between two
or more threads with the added feature of being able to recognize
when a thread has ended. This helps solves a problem where either:

  1) a mainline application waits forever on an event that will never be set
     because the thread that was supposed to set it has ended with an
     exception.
  2) a thread started by mainline waits forever on an event that will never be
     set because mainline, which was supposed to set it, has ended with an
     exception.


:Example: create a SmartEvent for mainline and a thread to use

>>> from scottbrian_utils.smart_event import SmartEvent
>>> import threading
>>> import time
>>> smart_event = SmartEvent(alpha=threading.current_thread())
>>> def f1(in_smart_event):
...     try:
...         time.sleep(3)
...         in_smart_event.set()
...     except RemoteThreadNotAlive as e:
...         print('mainline is not alive')
>>> f1_thread = threading.Thread(target=f1, args=(smart_event,)
>>> smart_event.set_thread(beta=f1_thread)
>>> f1_thread.start()
>>> try:
>>>     smart_event.wait()
>>> except RemoteThreadNotAlive:
>>>     print('Thread f1 is not alive')


The smart_event module contains:

    1) SmartEvent class with methods:

       a. wait
       b. set
       c. clear
       d. is_waiting
       e. is_set

"""
import time
import threading
from enum import Enum
from typing import (Any, Final, NamedTuple, Optional, Type, TYPE_CHECKING,
                    Union)

from scottbrian_utils.diag_msg import get_formatted_call_sequence

import logging

logger = logging.getLogger(__name__)
logging.getLogger(__name__).addHandler(logging.NullHandler())


###############################################################################
# SmartEvent class exceptions
###############################################################################
class SmartEventError(Exception):
    """Base class for exceptions in this module."""
    pass


class NeitherAlphaNorBetaSpecified(SmartEventError):
    """SmartEvent exception for no-op set_thread request."""
    pass


class IncorrectThreadSpecified(SmartEventError):
    """SmartEvent exception for incorrect thread specification."""
    pass


class DuplicateThreadSpecified(SmartEventError):
    """SmartEvent exception for duplicate thread specification."""
    pass


class ThreadAlreadySet(SmartEventError):
    """SmartEvent exception for thread already set."""
    pass


class BothAlphaBetaNotSet(SmartEventError):
    """SmartEvent exception for alpha or beta thread not set."""
    pass


class DetectedOpFromForeignThread(SmartEventError):
    """SmartEvent exception for attempted op from unregistered thread."""
    pass


class RemoteThreadNotAlive(SmartEventError):
    """SmartEvent exception for alpha or beta thread not alive."""
    pass


class WaitUntilTimeout(SmartEventError):
    """SmartEvent exception for wait_until timeout."""
    pass


class WaitDeadlockDetected(SmartEventError):
    """SmartEvent exception for wait deadlock detected."""
    pass


###############################################################################
# wait_until conditions
###############################################################################
WUCond = Enum('WUCond',
              'ThreadsReady RemoteWaiting RemoteSet')

###############################################################################
# SmartEvent class
###############################################################################
class SmartEvent():
    """Provides a coordination mechanism between two threads."""

    WAIT_UNTIL_TIMEOUT: Final[int] = 16

    class WorkSet(NamedTuple):
        current_thread: threading.Thread
        remote_thread: threading.Thread
        set_event: threading.Event
        wait_event: threading.Event

    def __init__(self,
                 alpha: Optional[threading.Thread] = None,
                 beta: Optional[threading.Thread] = None
                 ) -> None:
        """Initialize an instance of the SmartEvent class.

        Args:
            alpha: instance of a thread object that is used to determine
                     which event is to be set or waited on.
            beta: instance of a thread object that is used to determine
                     which event is to be set or waited on.

        Raises:
            IncorrectThreadSpecified: The alpha or beta arguments must be of
                                        type threading.Thread.
            DuplicateThreadSpecified: The alpha and beta arguments must be
                                        be for separate objects of type
                                        threading.Thread.

        """
        self.alpha_thread = None
        self.beta_thread = None
        self._both_threads_set = False

        if alpha or beta:
            self.set_thread(alpha, beta)

        self.alpha_event = threading.Event()
        self.beta_event = threading.Event()

        self.alpha_code = None
        self.beta_code = None

    ###########################################################################
    # repr
    ###########################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example: instantiate an SmartEvent

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> smart_event = SmartEvent()
        >>> repr(smart_event)
        SmartEvent()

        """
        if TYPE_CHECKING:
            __class__: Type[SmartEvent]
        classname = self.__class__.__name__
        parms = ''
        comma_space = ''
        if self.alpha_thread:
            parms += f'alpha={repr(self.alpha_thread)}'
            comma_space = ', '
        if self.beta_thread:
            parms += f'{comma_space}beta={repr(self.beta_thread)}'

        return f'{classname}({parms})'

    ###########################################################################
    # set_thread
    ###########################################################################
    def set_thread(self,
                   alpha: Optional[threading.Thread] = None,
                   beta: Optional[threading.Thread] = None
                   ) -> None:
        """Set alpha and/or beta thread.

        Args:
            alpha: instance of a thread object that is used to determine
                     which event is to be set or waited on.
            beta: instance of a thread object that is used to determine
                     which event is to be set or waited on.

        Raises:
            NeitherAlphaNorBetaSpecified:  One of alpha or beta must be
                                             specified for a set_threads
                                             request.
            IncorrectThreadSpecified: The alpha or beta arguments must be of
                                        type threading.Thread.
            DuplicateThreadSpecified: The alpha and beta arguments must be
                                        for separate objects of type
                                        threading.Thread.
            ThreadAlreadySet: The set_thread method detected that the
                                specified thread has already been set to
                                either a different or the same thread

        :Example: instantiate a SmartEvent and set the alpha thread

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> smart_event = SmartEvent()
        >>> smart_event.set_thread(alpha=threading.current_thread())

        """
        if not (alpha or beta):
            raise NeitherAlphaNorBetaSpecified(
                'One of alpha or beta must be specified for a '
                'set_threads request.')
        if ((alpha and not isinstance(alpha, threading.Thread))
                or (beta and not isinstance(beta, threading.Thread))):
            raise IncorrectThreadSpecified(
                'The alpha or beta arguments must be of type '
                'threading.Thread. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if ((alpha and alpha is self.beta_thread)
                or (beta and beta is self.alpha_thread)
                or (alpha and (alpha is beta))):
            raise DuplicateThreadSpecified(
                'The alpha and beta arguments must be be for separate '
                'objects of type threading.Thread. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if ((alpha and self.alpha_thread)
                or (beta and self.beta_thread)):
            raise ThreadAlreadySet(
                'The set_thread method detected that the specified '
                'thread has already been set to either a different or the '
                'same thread. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if alpha:
            self.alpha_thread = alpha
        if beta:
            self.beta_thread = beta

        if self.alpha_thread and self.beta_thread:
            self._both_threads_set = True

    ###########################################################################
    # wait
    ###########################################################################
    def wait(self,
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None) -> bool:
        """Wait on event.

        Args:
            log_msg: log msg to log
            timeout: number of seconds to wait for full queue to get free slot

        Return:
            True is the wait was successful, False if it timed out

        Raises:
            BothAlphaBetaNotSet: Both threads must be set before any
                                   SmartEvent services can be called
            DetectedOpFromForeignThread: The wait method must be called
                                           from either the alpha or the
                                           beta thread registered at time
                                           of instantiation or via the
                                           set_thread method
            RemoteThreadNotAlive: The wait service has detected that the
                                    alpha or beta thread is not alive
            WaitDeadlockDetected: Both threads are deadlocked, each waiting
                                    on their event.

        :Example: instantiate a SmartEvent and wait for function to set

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> import threading
        >>> def f1(smart_event: SmartEvent) -> None:
        ...     time.sleep(1)
        ...     smart_event.set()

        >>> a_smart_event = SmartEvent(alpha=threading.current_thread())
        >>> f1_thread = threading.Thread(target=f1, args=(a_smart_event,))
        >>> a_smart_event.set_thread(beta=f1_thread)
        >>> f1_thread.start()
        >>> a_smart_event.wait()
        >>> f1_thread.join()

        """
        work_set = self._get_work_set()

        if timeout and (timeout > 0):
            t_out = min(0.1, timeout)
        else:
            t_out = 0.1

        if log_msg:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            logger.debug(f'{caller_info} {log_msg}')

        start_time = time.time()
        while not work_set.wait_event.wait(timeout=t_out):
            if ((not work_set.remote_thread.is_alive())
                    and (not work_set.wait_event.is_set())):
                dead_thread = 'alpha' if work_set.remote_thread is \
                                              self.alpha_thread else 'beta'
                raise RemoteThreadNotAlive(
                    f'The wait service has detected that {dead_thread} thread '
                    'is not alive. '
                    f'Call sequence: {get_formatted_call_sequence()}')

            # Note that the following check must also check that we are
            # still waiting AFTER seeing that the remote is waiting. This is
            # to ensure we are not in the window where the above check in
            # the while statement was true and then while processing in the
            # body here the remote set our event and went into an immediate
            # wait which is perfectly fine.
            if ((len(work_set.set_event._cond._waiters) > 0)
                    and (not work_set.set_event.is_set())
                    and (not work_set.wait_event.is_set())):
                raise WaitDeadlockDetected('Both threads are '
                                           'deadlocked, each waiting on '
                                           'their event.')
            if timeout and (timeout < (time.time() - start_time)):
                return False

        work_set.wait_event.clear()  # be ready for next wait
        return True

    ###########################################################################
    # set
    ###########################################################################
    def set(self,
            log_msg: Optional[str] = None,
            code: Optional[Any] = None) -> None:
        """Set on event.

        Args:
            log_msg: log msg to log
            code: code that waiter can retrieve with get_code

        Raises:
            BothAlphaBetaNotSet: Both threads must be set before any
                                   SmartEvent services can be called
            DetectedOpFromForeignThread: The set method must be called
                                           from either the alpha or the
                                           beta thread registered at time
                                           of instantiation or via the
                                           set_thread method
            RemoteThreadNotAlive: The set service has detected that the
                                    alpha or beta thread is not alive

        :Example: instantiate SmartEvent and set event that function waits on

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> import threading
        >>> def f1(smart_event: SmartEvent) -> None:
        ...     smart_event.wait()

        >>> a_smart_event = SmartEvent(alpha=threading.current_thread())
        >>> f1_thread = threading.Thread(target=f1, args=(a_smart_event,))
        >>> a_smart_event.set_thread(beta=f1_thread)
        >>> f1_thread.start()
        >>> time.sleep(1)
        >>> a_smart_event.set()
        >>> f1_thread.join()

        """
        work_set = self._get_work_set()

        if log_msg:  # if caller specified a log message to issue
            # we want the prior 2 callers (latest=1, depth=2)
            logger.debug(f'{get_formatted_call_sequence(latest=1, depth=2)} '
                         f'{log_msg}')

        if not work_set.remote_thread.is_alive():
            dead_thread = 'alpha' if work_set.remote_thread is \
                                     self.alpha_thread else 'beta'
            raise RemoteThreadNotAlive(
                f'The set service has detected that {dead_thread} thread '
                'is not alive. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if code:  # if caller specified a code for the remote thread
            if work_set.remote_thread is self.alpha_thread:
                self.alpha_code = code
            else:
                self.beta_code = code

        work_set.set_event.set()  # wake remote thread

    ###########################################################################
    # get_code
    ###########################################################################
    def get_code(self) -> Any:
        """Get code from last set.

        Returns:
            The code set by the thread that did the set event

        Raises:
            BothAlphaBetaNotSet: Both threads must be set before any
                                   SmartEvent services can be called
            DetectedOpFromForeignThread: The get_code method must be called
                                           from either the alpha or the
                                           beta thread registered at time
                                           of instantiation or via the
                                           set_thread method
            RemoteThreadNotAlive: The set service has detected that the
                                    alpha or beta thread is not alive

        :Example: instantiate SmartEvent and set event that function waits on

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> import threading
        >>> def f1(smart_event: SmartEvent) -> None:
        ...     smart_event.wait()

        >>> a_smart_event = SmartEvent(alpha=threading.current_thread())
        >>> f1_thread = threading.Thread(target=f1, args=(a_smart_event,))
        >>> a_smart_event.set_thread(beta=f1_thread)
        >>> f1_thread.start()
        >>> time.sleep(1)
        >>> a_smart_event.set()
        >>> f1_thread.join()

        """
        work_set = self._get_work_set()
        if work_set.current_thread is self.alpha_thread:
            return self.alpha_code
        else:
            return self.beta_code

    ###########################################################################
    # get_work_set
    ###########################################################################
    def _get_work_set(self) -> WorkSet:
        """Get the remote thread and events for the current thread.

        Raises:
            BothAlphaBetaNotSet: Both threads must be set before wait_until
                                   can be called to wait until the remote is
                                   waiting
            DetectedOpFromForeignThread: The wait_until method must be
                                           called from either the alpha or
                                           the beta thread registered at time
                                            of instantiation or via the
                                            set_thread method
            WaitUntilTimeout: The wait_until method timed out

        Returns:
            A WorkSet named tuple with the remote thread and events

        """
        if not self._both_threads_set:
            raise BothAlphaBetaNotSet(
                'Both threads must be set before any '
                'SmartEvent services can be called. '
                f'Call sequence: {get_formatted_call_sequence(1,2)}')
        current_thread = threading.current_thread()
        if current_thread is self.alpha_thread:
            return SmartEvent.WorkSet(current_thread=current_thread,
                                      remote_thread=self.beta_thread,
                                      set_event=self.alpha_event,
                                      wait_event=self.beta_event)
        elif current_thread is self.beta_thread:
            return SmartEvent.WorkSet(current_thread=current_thread,
                                      remote_thread=self.alpha_thread,
                                      set_event=self.beta_event,
                                      wait_event=self.alpha_event)
        else:
            raise DetectedOpFromForeignThread(
                'The wait method must be called from either the alpha or '
                'the beta thread registered at time of instantiation or '
                'via the set_thread method. '
                f'Call sequence: {get_formatted_call_sequence(1,2)}')

    ###########################################################################
    # wait_until
    ###########################################################################
    def wait_until(self,
                   cond: WUCond,
                   timeout: Optional[Union[int, float]] = None
                   ) -> None:
        """Wait until both threads have been set and/or remote is waiting.

        Args:
            cond: specifies to either wait for both threads to be
                    set (WUCond.ThreadsReady) or for the remote to
                    be waiting (WUCond.RemoteWaiting)
            timeout: number of seconds to allow for wait_until to succeed

        Raises:
            BothAlphaBetaNotSet: Both threads must be set before wait_until
                                   can be called to wait until the remote is
                                   waiting
            DetectedOpFromForeignThread: The wait_until method must be
                                           called from either the alpha or
                                           the beta thread registered at time
                                            of instantiation or via the
                                            set_thread method
            WaitUntilTimeout: The wait_until method timed out

        :Example: instantiate SmartEvent and wait for ready

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> import threading
        >>> def f1(smart_event: SmartEvent) -> None:
        ...     smart_event.set_thread(beta=threading.current_thread())
        ...     smart_event.wait()

        >>> a_smart_event = SmartEvent(alpha=threading.current_thread())
        >>> f1_thread = threading.Thread(target=f1, args=(a_smart_event,))
        >>> f1_thread.start()
        >>> a_smart_event.wait_until(WUCond.ThreadsReady)
        >>> a_smart_event.set()
        >>> f1_thread.join()

        """
        if timeout and (timeout > 0):
            t_out = min(0.1, timeout)
        else:
            t_out = 0.1
        start_time = time.time()

        #######################################################################
        # Handle ThreadsReady
        #######################################################################
        if cond == WUCond.ThreadsReady:
            while not (self._both_threads_set
                       and self.alpha_thread.is_alive()
                       and self.beta_thread.is_alive()):
                if timeout and (timeout < (time.time() - start_time)):
                    raise WaitUntilTimeout(
                        'The wait_until method timed out. '
                        f'Call sequence: {get_formatted_call_sequence()}')
                time.sleep(t_out)

        #######################################################################
        # Handle RemoteWaiting
        #######################################################################
        elif cond == WUCond.RemoteWaiting:
            work_set = self._get_work_set()
            while len(work_set.set_event._cond._waiters) == 0:
                if not work_set.remote_thread.is_alive():
                    dead_thread = 'alpha' if work_set.remote_thread is \
                                             self.alpha_thread else 'beta'
                    raise RemoteThreadNotAlive(
                        f'The wait service has detected that {dead_thread} '
                        'thread is not alive. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                if timeout and (timeout < (time.time() - start_time)):
                    raise WaitUntilTimeout(
                        'The wait_until method timed out. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                time.sleep(t_out)

        #######################################################################
        # Handle RemoteSet
        #######################################################################
        elif cond == WUCond.RemoteSet:
            work_set = self._get_work_set()
            while not work_set.wait_event.is_set():
                if not work_set.remote_thread.is_alive():
                    dead_thread = 'alpha' if work_set.remote_thread is \
                                             self.alpha_thread else 'beta'
                    raise RemoteThreadNotAlive(
                        f'The wait service has detected that {dead_thread} '
                        'thread is not alive. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                if timeout and (timeout < (time.time() - start_time)):
                    raise WaitUntilTimeout(
                        'The wait_until method timed out. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                time.sleep(t_out)
