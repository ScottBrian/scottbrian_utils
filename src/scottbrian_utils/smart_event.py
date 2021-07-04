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
from typing import (Any, Final, Optional, Tuple, Type,
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


class ConflictDeadlockDetected(SmartEventError):
    """SmartEvent exception for conflicting requests."""
    pass


class InconsistentFlagSettings(SmartEventError):
    """SmartEvent exception for flag setting that are not valid."""
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
        """ThreadEvent class contains thread, events, and flags."""
        name: str
        thread: threading.Thread = None
        event: threading.Event = None
        sync_event: threading.Event = None
        code: Any = None
        waiting: bool = False
        sync_wait: bool = False
        timeout_specified: bool = False
        deadlock: bool = False
        conflict: bool = False

    def __init__(self, *,
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
        self.sync_cleanup = False
        self.debug_logging_enabled = logger.isEnabledFor(logging.DEBUG)

        self.alpha = SmartEvent.ThreadEvent(name='alpha',
                                            event=threading.Event(),
                                            sync_event=threading.Event())
        self.beta = SmartEvent.ThreadEvent(name='beta',
                                           event=threading.Event(),
                                           sync_event=threading.Event())

        if alpha or beta:
            self.set_thread(alpha=alpha, beta=beta)

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
    def set_thread(self, *,
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
            logger.debug('raising NeitherAlphaNorBetaSpecified')
            raise NeitherAlphaNorBetaSpecified(
                'One of alpha or beta must be specified for a '
                'set_threads request. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if ((alpha and not isinstance(alpha, threading.Thread))
                or (beta and not isinstance(beta, threading.Thread))):
            logger.debug('raising IncorrectThreadSpecified')
            raise IncorrectThreadSpecified(
                'The alpha and beta arguments must be of type '
                'threading.Thread. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if ((alpha and alpha is self.beta.thread)
                or (beta and beta is self.alpha.thread)
                or (alpha and (alpha is beta))):
            logger.debug('raising DuplicateThreadSpecified')
            raise DuplicateThreadSpecified(
                'The alpha and beta arguments must be be for separate '
                'and distinct objects of type threading.Thread. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if ((alpha and self.alpha.thread)
                or (beta and self.beta.thread)):
            logger.debug('raising ThreadAlreadySet')
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
    def sync(self, *,
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None) -> bool:
        """Sync up the threads.

        Args:
            log_msg: log msg to log
            timeout: number of seconds to allow for sync to happen

        Returns:
            True is the sync was successful, False if it timed out

        Raises:
            RemoteThreadNotAlive: The sync service has detected that '
                                  remote thread is not alive.

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
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            logger.debug(f'sync entered {caller_info} {log_msg}')

        # current.sync_wait = True

        # if current.name == 'alpha':
        #     ret_value = self.wait(timeout=timeout)  # , sync=True)
        #     self.set()
        # else:
        #     self.set()
        #     ret_value = self.wait(timeout=timeout)  # , sync=True)
        start_time = time.time()
        current.waiting = True
        current.sync_wait = True
        ret_code = self.wait(timeout=timeout)
        if ret_code:
            # Flip the cleanup flag. If it was False, then we
            # will set it to True and then wait for the remote
            # to set it back to False which will mean that
            # both threads have reset the waiting, sync_wait,
            # and event flags. If it was true, then the remote
            # did the flip and we will flip it to false.
            with self._wait_check_lock:
                self.sync_cleanup = not self.sync_cleanup
            while self.sync_cleanup:
                with self._wait_check_lock:
                    if not self.sync_cleanup:
                        break  # all done
                    if not remote.thread.is_alive():
                        logger.debug(
                            f'{current.name} raising '
                            'RemoteThreadNotAlive')
                        raise RemoteThreadNotAlive(
                            'The sync service has detected that '
                            f'{remote.name} thread is not alive. '
                            f'Call sequence: {get_formatted_call_sequence()}')

                    if timeout and (timeout < (time.time() - start_time)):
                        logger.debug(f'{current.name} timeout of a sync '
                                     'request.')
                        ret_code = False
                        break
                time.sleep(0.1)

        if log_msg and self.debug_logging_enabled:
            logger.debug(f'sync exiting with ret_code {ret_code} '
                         f'{caller_info} {log_msg}')

        return ret_code

    ###########################################################################
    # wait
    ###########################################################################
    def wait(self, *,
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None) -> bool:
        """Wait on event.

        Args:
            log_msg: log msg to log
            timeout: number of seconds to allow for wait to complete

        Returns:
            True if timeout was not specified, or if it was specified and
              the wait request completed within the specified number of
              seconds. False if timeout was specified and the wait
              request did not complete within the specified number of
              seconds.

        Raises:
            RemoteThreadNotAlive: The wait service has detected that the
                                    alpha or beta thread is not alive
            WaitDeadlockDetected: Both threads are deadlocked, each waiting
                                    on the other to set their event.
            ConflictDeadlockDetected: A sync request was made by
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
            current.timeout_specified = True
        else:
            t_out = 0.1
            current.timeout_specified = False

        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            logger.debug(f'wait entered {caller_info} {log_msg}')

        #  logger.debug(f'{current.name} about to enter wait loop')
        current.waiting = True
        current_set_remote_sync_event = False
        start_time = time.time()
        # cases for current is doing sync_wait:
        # if current sees beta not waiting, OK - needs time to catch up
        # if current sees beta waiting and event is set - OK - needs time
        # if current sees beta waiting and event not set - hopeless
        while True:
            if current.sync_wait:
                ret_code = remote.sync_event.wait(timeout=t_out)
                if ret_code and current_set_remote_sync_event:
                    # Set the waiting and sync_waiting flags under lock.
                    # They are checked by remote under lock and the remote
                    # could get confused is either flag is set to False
                    # before the other is set to False. See below where
                    # remote_is_sync_waiting and remote_is_normal_waiting
                    # are set. Also, see set InconsistentFlagSettings.
                    with self._wait_check_lock:
                        current.waiting = False
                        current.sync_wait = False
                        remote.sync_event.clear()  # be ready for next wait
                    # return ret_code
                    break
            else:
                ret_code = remote.event.wait(timeout=t_out)
                if ret_code:
                    with self._wait_check_lock:
                        current.waiting = False
                        remote.event.clear()  # be ready for next wait
                    # return ret_code
                    break

            # We need to do the following checks while locked to prevent
            # either thread from setting the other thread's flags AFTER
            # the other thread has already detected those
            # conditions, set the flags, left, and is back with a new
            # request.
            with self._wait_check_lock:
                # Now that we have the lock we need to determine whether
                # we were set between the call getting the
                if current.sync_wait:
                    if (remote.sync_event.is_set()
                            and current_set_remote_sync_event):
                        current.waiting = False
                        current.sync_wait = False
                        remote.sync_event.clear()  # be ready 4 next sync
                        ret_code = True
                        break
                        # return True
                else:
                    if remote.event.is_set():
                        current.waiting = False
                        current.sync_wait = False
                        remote.event.clear()  # be ready for next wait
                        ret_code = True
                        break
                        # return True

                # Check for error conditions first before checking
                # whether the remote is alive. If the remote detects a
                # deadlock or conflict issue, it will set the current
                # sides bit and then raise an error and will likely be
                # gone when we check. we want to raise the same error on
                # this side.

                # current.deadlock is set only by the remote. So, if
                # current.deadlock is True, then remote has already
                # detected the deadlock, set our flag, raised
                # the deadlock on its side, and is now possibly in a new
                # wait. If current.deadlock if False, and remote is waiting
                # and is not set then it will not be getting set by us
                # since we are also waiting. So, we set remote.deadlock
                # to tell it, and then we raise the error on our side.
                # But, we don't do this if the remote.deadlock is
                # already on as that suggests that we already told
                # remote and raised the error, which implies that we are
                # in a new wait and the remote has not yet woken up to
                # deal with the earlier deadlock. We can simply ignore
                # it for now.
                remote_is_normal_waiting = False
                remote_is_sync_waiting = False
                raise_deadlock = False
                raise_conflict = False
                if remote.waiting and not remote.deadlock:
                    if remote.sync_wait:
                        if not current.sync_event.is_set():
                            remote_is_sync_waiting = True
                    else:
                        if not remote.event.is_set():
                            remote_is_normal_waiting = True

                if not current.deadlock:
                    if current.sync_wait:
                        if (remote_is_normal_waiting and
                                not (current.timeout_specified
                                     or remote.timeout_specified)):
                            remote.deadlock = True
                            remote.conflict = True
                            raise_conflict = True
                        elif (remote_is_sync_waiting
                                and not current_set_remote_sync_event):
                            current.sync_event.set()
                            current_set_remote_sync_event = True

                    else:
                        if (remote_is_sync_waiting and
                                not (current.timeout_specified
                                     or remote.timeout_specified)):
                            remote.deadlock = True
                            remote.conflict = True
                            raise_conflict = True
                        elif (remote_is_normal_waiting and
                                not (current.timeout_specified
                                     or remote.timeout_specified)):
                            remote.deadlock = True
                            remote.conflict = False
                            raise_deadlock = True
                else:
                    if current.conflict:
                        raise_conflict = True
                    else:
                        raise_deadlock = True

                if raise_deadlock:
                    current.waiting = False
                    current.sync_wait = False
                    current.deadlock = False
                    current.conflict = False
                    logger.debug(f'{current.name} raising '
                                 'WaitDeadlockDetected')
                    raise WaitDeadlockDetected(
                        'Both threads are deadlocked, each waiting on '
                        'the other to set their event.')
                elif raise_conflict:
                    current.waiting = False
                    current.sync_wait = False
                    current.deadlock = False
                    current.conflict = False
                    logger.debug(
                        f'{current.name} raising '
                        'ConflictDeadlockDetected')
                    raise ConflictDeadlockDetected(
                        'A sync request was made by thread '
                        f'{current.name} but remote thread '
                        f'{remote.name} detected deadlock instead '
                        'which indicates that the remote '
                        'thread did not make a matching sync '
                        'request.')

                if not remote.thread.is_alive():
                    current.waiting = False
                    current.sync_wait = False
                    logger.debug(
                        f'{current.name} raising '
                        'RemoteThreadNotAlive')
                    raise RemoteThreadNotAlive(
                        'The wait service has detected that '
                        f'{remote.name} thread is not alive. '
                        f'Call sequence: {get_formatted_call_sequence()}')

                if timeout and (timeout < (time.time() - start_time)):
                    logger.debug(f'{current.name} timeout of a wait '
                                 'request with current.waiting = '
                                 f'{current.waiting} and '
                                 f'current.sync_wait = {current.sync_wait}')
                    current.waiting = False
                    current.sync_wait = False
                    ret_code = False
                    break

        if log_msg and self.debug_logging_enabled:
            logger.debug(f'wait exiting with ret_code {ret_code} '
                         f'{caller_info} {log_msg}')

        return ret_code

    ###########################################################################
    # set
    ###########################################################################
    def set(self, *,
            log_msg: Optional[str] = None,
            timeout: Optional[Union[int, float]] = None,
            code: Optional[Any] = None) -> bool:
        """Set on event.

        Args:
            log_msg: log msg to log
            timeout: number of seconds to allow for set to complete
            code: code that waiter can retrieve with get_code

        Returns:
            True if timeout was not specified, or if it was specified and
              the set request completed within the specified number of
              seconds. False if timeout was specified and the set
              request did not complete within the specified number of
              seconds.

        Raises:
            RemoteThreadNotAlive: The set service has detected that the
                                    alpha or beta thread is not alive
            InconsistentFlagSettings: The remote ThreadEvent flag settings
                                         are not valid.

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
        code_msg = f' with code: {code} ' if code else ' '

        # if caller specified a log message to issue
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            logger.debug(f'set entered{code_msg}'
                         f'{caller_info} {log_msg}')

        start_time = time.time()
        while True:
            with self._wait_check_lock:
                if not remote.thread.is_alive():
                    logger.debug(f'{current.name} raising '
                                 'RemoteThreadNotAlive')
                    raise RemoteThreadNotAlive(
                        f'The set service has detected that {remote.name} '
                        'thread is not alive. '
                        f'Call sequence: {get_formatted_call_sequence()}')

                # error cases
                # 1) waiting False and sync_wait True
                # 2) waiting False and deadlock True
                # 3) waiting False and conflict True
                # 4) deadlock False and conflict True
                if (((not remote.waiting)
                        and (remote.sync_wait
                             or remote.deadlock
                             or remote.conflict))
                        or (remote.conflict and not remote.deadlock)):
                    logger.debug(f'{current.name} raising '
                                 'InconsistentFlagSettings. '
                                 f'waiting: {remote.waiting}, '
                                 f'sync_wait: {remote.sync_wait}, '
                                 f'deadlock: {remote.deadlock}, '
                                 f'conflict: {remote.conflict}, ')
                    raise InconsistentFlagSettings(
                        'The remote ThreadEvent flag settings are not valid.')

                # cases where we loop until remote is ready
                # 1) remote waiting and event already set
                # 2) remote waiting and deadlock
                # 3) remote not waiting and event set

                # cases where we do the set:
                # 1) remote is not waiting and event not set
                # 2) remote is normal waiting and event not set and not
                #    deadlock
                # 3) remote is sync waiting and event not set
                if not (current.event.is_set() or remote.deadlock):
                    if code:  # if caller specified a code for remote thread
                        remote.code = code

                    # logger.debug(
                    #     f'{current.name} about to set event {code_msg} '
                    #     f'{get_formatted_call_sequence(latest=1, depth=2)} ')
                    current.event.set()  # wake remote thread
                    ret_code = True
                    break

                if timeout and (timeout < (time.time() - start_time)):
                    logger.debug(f'{current.name} timeout of a set '
                                 'request with current.event.is_set() = '
                                 f'{current.event.is_set()} and '
                                 f'remote.deadlock = '
                                 f'{remote.deadlock}')
                    current.waiting = False
                    current.sync_wait = False
                    ret_code = False
                    break

            time.sleep(0.2)

        # if caller specified a log message to issue
        if log_msg and self.debug_logging_enabled:
            logger.debug(f'set exiting with ret_code {ret_code} '
                         f'{caller_info} {log_msg}')
        return ret_code

    ###########################################################################
    # get_code
    ###########################################################################
    def get_code(self) -> Any:
        """Get code from last set.

        Returns:
            The code set by the thread that did the set event

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
            RemoteThreadNotAlive: The wait_until service has detected that
                                  remote thread is not alive.
            WaitUntilTimeout: The wait_until method timed out.

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
                    logger.debug('raising  WaitUntilTimeout')
                    raise WaitUntilTimeout(
                        'The wait_until method timed out. '
                        f'Call sequence: {get_formatted_call_sequence()}')
                time.sleep(t_out)

        #######################################################################
        # Handle RemoteWaiting
        #######################################################################
        elif cond == WUCond.RemoteWaiting:
            current, remote = self._get_current_remote()
            while True:
                # make sure we are waiting for a new set, meaning that
                # the event is not set and we are not doing a sync wait
                # which may indicate the thread did not get control
                # yet to return from a previous set or sync
                if (remote.waiting
                        and not current.event.is_set()
                        and not remote.sync_wait):
                    return

                if not remote.thread.is_alive():
                    logger.debug(f'{current.name} raising '
                                 'RemoteThreadNotAlive')
                    raise RemoteThreadNotAlive(
                        f'The wait_until service has detected that'
                        f' {remote.name}  thread is not alive. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                if timeout and (timeout < (time.time() - start_time)):
                    logger.debug(f'{current.name} raising '
                                 'WaitUntilTimeout')
                    raise WaitUntilTimeout(
                        'The wait_until method timed out. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                time.sleep(t_out)

        #######################################################################
        # Handle RemoteSet
        #######################################################################
        elif cond == WUCond.RemoteSet:
            current, remote = self._get_current_remote()
            while not remote.event.is_set():
                if not remote.thread.is_alive():
                    logger.debug(f'{current.name} raising '
                                 'RemoteThreadNotAlive')
                    raise RemoteThreadNotAlive(
                        f'The wait_until service has detected that'
                        f' {remote.name} thread is not alive. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                if timeout and (timeout < (time.time() - start_time)):
                    logger.debug(f'{current.name} raising '
                                 'WaitUntilTimeout')
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

        Returns:
            The current and remote ThreadEvent objects

        """
        if not self._both_threads_set:
            logger.debug('raising BothAlphaBetaNotSet')
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
            logger.debug('raising DetectedOpFromForeignThread')
            raise DetectedOpFromForeignThread(
                'The wait method must be called from either the alpha or '
                'the beta thread registered at time of instantiation or '
                'via the set_thread method. '
                f'Call sequence: {get_formatted_call_sequence(1,2)}')
