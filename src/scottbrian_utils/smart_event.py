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
from dataclasses import dataclass
from typing import (Any, Final, NamedTuple, Optional, Tuple, Type,
                    TYPE_CHECKING, Union)

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


class ConflictingSyncAndDeadlockDetected(SmartEventError):
    """SmartEvent exception for conflicting requests."""
    pass


###############################################################################
# wait_until conditions
###############################################################################
WUCond = Enum('WUCond',
              'ThreadsReady RemoteWaiting RemoteSet')


###############################################################################
# ThreadEvent Class
###############################################################################
# @dataclass
# class ThreadEvent:
#     thread: threading.Thread = None
#     event: threading.Event = threading.Event()
#     code: Any = None
#     waiting: bool = False
#     sync_wait: bool = False


###############################################################################
# SmartEvent class
###############################################################################
class SmartEvent:
    """Provides a coordination mechanism between two threads."""

    WAIT_UNTIL_TIMEOUT: Final[int] = 16

    ###########################################################################
    # ThreadEvent Class
    ###########################################################################
    @dataclass
    class ThreadEvent:
        name: str
        thread: threading.Thread = None
        event: threading.Event = threading.Event()
        code: Any = None
        waiting: bool = False
        sync_wait: bool = False

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

        """
        self._wait_check_lock = threading.Lock()
        self._both_threads_set = False
        self._sync_detected = False
        self._deadlock_detected = False

        self.alpha = SmartEvent.ThreadEvent(name='alpha')
        self.beta = SmartEvent.ThreadEvent(name='beta')

        if alpha or beta:
            self.set_thread(alpha, beta)

    ###########################################################################
    # repr
    ###########################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example: instantiate a SmartEvent and call repr

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
        if self.alpha.thread:
            parms += f'alpha={repr(self.alpha.thread)}'
            comma_space = ', '
        if self.beta.thread:
            parms += f'{comma_space}beta={repr(self.beta.thread)}'

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
            IncorrectThreadSpecified: The alpha and beta arguments must be of
                                        type threading.Thread.
            DuplicateThreadSpecified: The alpha and beta arguments must be
                                        for separate and distinct objects of
                                        type threading.Thread.
            ThreadAlreadySet: The set_thread method detected that the
                                specified thread has already been set to
                                either a different or the same input thread.

        :Example: instantiate a SmartEvent and set the alpha thread

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> smart_event = SmartEvent()
        >>> smart_event.set_thread(alpha=threading.current_thread())

        """
        if not (alpha or beta):
            raise NeitherAlphaNorBetaSpecified(
                'One of alpha or beta must be specified for a '
                'set_threads request. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if ((alpha and not isinstance(alpha, threading.Thread))
                or (beta and not isinstance(beta, threading.Thread))):
            raise IncorrectThreadSpecified(
                'The alpha and beta arguments must be of type '
                'threading.Thread. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if ((alpha and alpha is self.beta.thread)
                or (beta and beta is self.alpha.thread)
                or (alpha and (alpha is beta))):
            raise DuplicateThreadSpecified(
                'The alpha and beta arguments must be be for separate '
                'and distinct objects of type threading.Thread. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if ((alpha and self.alpha.thread)
                or (beta and self.beta.thread)):
            raise ThreadAlreadySet(
                'The set_thread method detected that the specified '
                'thread has already been set to either a different or the '
                'same input thread. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if alpha:
            self.alpha.thread = alpha
        if beta:
            self.beta.thread = beta

        if self.alpha.thread and self.beta.thread:
            self._both_threads_set = True

    ###########################################################################
    # sync
    ###########################################################################
    def sync(self,
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None) -> bool:
        """Sync up the threads.

        Args:
            log_msg: log msg to log
            timeout: number of seconds to allow for sync to happen

        Return:
            True is the sync was successful, False if it timed out

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
                                    on the other to set their event.
            ConflictingSyncAndDeadlockDetected: A sync request was made by
                                                  the current thread but the
                                                  but the remote thread
                                                  detected deadlock instead
                                                  which indicates that the
                                                  remote thread did not make a
                                                  matching sync request.

        :Example: instantiate a SmartEvent and sync the threads

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> import threading
        >>> def f1(smart_event: SmartEvent) -> None:
        ...     smart_event.sync()

        >>> smart_event = SmartEvent(alpha=threading.current_thread())
        >>> f1_thread = threading.Thread(target=f1, args=(smart_event,))
        >>> smart_event.set_thread(beta=f1_thread)
        >>> f1_thread.start()
        >>> smart_event.sync()
        >>> f1_thread.join()

        """
        current, remote = self._get_current_remote()

        if log_msg:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            logger.debug(f'{caller_info} {log_msg}')

        current.sync_wait = True
        remote.event.wait(timeout=timeout)

    ###########################################################################
    # wait
    ###########################################################################
    def wait(self,
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None) -> bool:
        """Wait on event.

        Args:
            log_msg: log msg to log
            timeout: number of seconds to allow for wait

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
                                    on the other to set their event.
            ConflictingSyncAndDeadlockDetected: A sync request was made by
                                                  the current thread but the
                                                  but the remote thread
                                                  detected deadlock instead
                                                  which indicates that the
                                                  remote thread did not make a
                                                  matching sync request.

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
        current, remote = self._get_current_remote()

        if timeout and (timeout > 0):
            t_out = min(0.1, timeout)
        else:
            t_out = 0.1

        if log_msg:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            logger.debug(f'{caller_info} {log_msg}')

        try:
            current.waiting = True
            start_time = time.time()
            while ((not remote.event.wait(timeout=t_out))
                    or self._sync_detected
                    or self._deadlock_detected):
                # We need to do the following checks while locked to prevent
                # either
                # thread from setting the other thread's deadlock flag AFTER
                # the other thread has already detected deadlock and is now
                # gone.
                # The proper protocol for deadlock detection is:
                # obtain the lock
                # if remote thread waiting or deadlock flag
                #     if our deadlock flag is False
                #         set remote deadlock flag
                #     set our deadlock flag to False
                #     raise deadlock
                with self._wait_check_lock:
                    if not (remote.thread.is_alive()
                            or remote.event.is_set()
                            or self._sync_detected
                            or self._deadlock_detected):
                        dead_thread = remote.name
                        raise RemoteThreadNotAlive(
                            f'The wait service has detected that {dead_thread} '
                            'thread is not alive. '
                            f'Call sequence: {get_formatted_call_sequence()}')

                    # Note that the following check must also check that we are
                    # still waiting AFTER seeing that the remote is waiting.
                    # This
                    # is to ensure we are not in the window where the above
                    # check in the while statement was true and then while
                    # processing in the body here the remote set our event and
                    # went into an immediate wait which is perfectly fine.
                    if (remote.waiting
                            and not (current.event.is_set()
                                     or remote.event.is_set())
                            or self._sync_detected
                            or self._deadlock_detected):

                        if current.sync_wait:
                            if self._deadlock_detected:
                                # reset both flags
                                self._sync_detected = False
                                self._deadlock_detected = False
                                raise ConflictingSyncAndDeadlockDetected(
                                    'A sync request was made by thread '
                                    f'{current.name} but remote thread '
                                    f'{remote.name} detected deadlock instead '
                                    'which indicates that the remote '
                                    'thread did not make a matching sync '
                                    'request.')
                            # Flip the sync detected flag. If we discover sync
                            # first, flipping will set the flag to True to
                            # notify the remote. Otherwise, if remote
                            # flipped the flag to true to let us know sync
                            # was detected, our flip will set it to False.
                            self._sync_detected = not self._sync_detected
                            return True
                        else:
                            if self._sync_detected:
                                # reset both flags
                                self._sync_detected = False
                                self._deadlock_detected = False
                                raise ConflictingSyncAndDeadlockDetected(
                                    'A sync request appears to have been '
                                    f'made by remote thread {remote.name} but '
                                    f'the current thread {current.name} '
                                    'did not make a matching sync '
                                    'request.')

                        # Flip the deadlock_detected flag. If on, then remote
                        # saw the deadlock first and now we must set the flag
                        # back to False. If off, then we are seeing the
                        # deadlock and must set the flag True to notify the
                        # remote thread who will turn it back to False.
                        self._deadlock_detected = not self._deadlock_detected
                        raise WaitDeadlockDetected(
                            'Both threads are deadlocked, each waiting on '
                            'the other to set their event.')

                    if timeout and (timeout < (time.time() - start_time)):
                        # make sure remote does not see us waiting
                        current.waiting = False
                        current.sync_wait = False
                        return False
        finally:
            current.waiting = False
            current.sync_wait = False
            remote.event.clear()  # be ready for next wait

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
        current, remote = self._get_current_remote()

        if log_msg:  # if caller specified a log message to issue
            # we want the prior 2 callers (latest=1, depth=2)
            logger.debug(f'{get_formatted_call_sequence(latest=1, depth=2)} '
                         f'{log_msg}')

        if not remote.thread.is_alive():
            dead_thread = remote.name
            raise RemoteThreadNotAlive(
                f'The set service has detected that {dead_thread} thread '
                'is not alive. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if code:  # if caller specified a code for the remote thread
            remote.code = code
            # if work_set.remote_thread is self.alpha_thread:
            #     self.alpha_code = code
            # else:
            #     self.beta_code = code

        current.event.set()  # wake remote thread

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
        current, _ = self._get_current_remote()
        return current.code

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
                       and self.alpha.thread.is_alive()
                       and self.beta.thread.is_alive()):
                if timeout and (timeout < (time.time() - start_time)):
                    raise WaitUntilTimeout(
                        'The wait_until method timed out. '
                        f'Call sequence: {get_formatted_call_sequence()}')
                time.sleep(t_out)

        #######################################################################
        # Handle RemoteWaiting
        #######################################################################
        elif cond == WUCond.RemoteWaiting:
            current, remote = self._get_current_remote()
            while len(current.event._cond._waiters) == 0:
                if not remote.thread.is_alive():
                    dead_thread = remote.name
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
            while not work_set.remote.event.is_set():
                if not work_set.remote.thread.is_alive():
                    dead_thread = work_set.remote.name
                    raise RemoteThreadNotAlive(
                        f'The wait service has detected that {dead_thread} '
                        'thread is not alive. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                if timeout and (timeout < (time.time() - start_time)):
                    raise WaitUntilTimeout(
                        'The wait_until method timed out. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                time.sleep(t_out)

    ###########################################################################
    # _get_current_remote
    ###########################################################################
    def _get_current_remote(self) -> Tuple[ThreadEvent, ThreadEvent]:
        """Get the current and remote ThreadEvent objects.

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
            The current and remote ThreadEvent objects

        """
        if not self._both_threads_set:
            raise BothAlphaBetaNotSet(
                'Both threads must be set before any '
                'SmartEvent services can be called. '
                f'Call sequence: {get_formatted_call_sequence(1,2)}')
        current_thread = threading.current_thread()
        if current_thread is self.alpha.thread:
            return self.alpha, self.beta

        elif current_thread is self.beta.thread:
            return self.beta, self.alpha

        else:
            raise DetectedOpFromForeignThread(
                'The wait method must be called from either the alpha or '
                'the beta thread registered at time of instantiation or '
                'via the set_thread method. '
                f'Call sequence: {get_formatted_call_sequence(1,2)}')