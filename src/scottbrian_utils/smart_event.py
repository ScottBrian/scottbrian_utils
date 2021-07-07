"""Module smart_event.

=============
SmartEvent
=============

You can use the SmartEvent class to coordinate activities between two
threads. We will call these threads alpha and beta. The coordination is
accomplished using either of two services: ``wait()``/``resume()`` and
``sync()``.

With the ``wait()``/``resume()`` scheme, one thread typically gives another
thread a task to do and then does a ``wait()'' until the other thread
signals that the task is complete by doing a ``resume()``.  It does not matter
which thread does the waiting and which thread aoes the resumimg, as long as
one thread's ``wait()`` is matched by the other thread with a ``resume()``.
For example, alpha could do a ``wait()`` and beta the ``resume()'' in one
section of code, and later on beta does the ``wait()'' with alpha doing the
``resume()''. Also, the ``resume()`` can preceed the ``wait()'', known as a
**pre-resume**, which will allow the ``wait()`` to proceed imediately.

The SmartEvent ``sync()`` request is used to ensure that two threads have
each reached a processing sync-point, and are then allowed to
proceed from that sync-point at the same time. The first thread to do the
``sync()`` request is paused until the second thread does a matching
``sync()`` request, at which time both threads are allowed to proceed.

One thing to consider is that when we talk of allowing one or both threads
to proceed, the thread processing we are doing here is a multi-tasking
and **not** multi-processing. So in reality, doing a ``resume()`` or a
``sync()`` will not neccessarily cause the other thread to be given
control, only that it is now eligible to be given control as determined by
the python and/or the operating system.

One of the important features of SmartEvent is that it will detect when a
``wait()`` or ``sync()`` will not result in success because either the other
thread becomes inactive or because the other thread has issued a ``wait()``
request which now places both threads in a deadlock. When this happens, a
**RemoteThreadNotAlive**, **WaitDeadlockDetected**, or
**ConflictDeadlockDetected** error will be raised.

SmartEvent is easy to use - just instantiate it,register the alpha
and beta threads, and its ready to go. Following are some examples.


:Example: create a SmartEvent for mainline and a thread to use

>>> from scottbrian_utils.smart_event import SmartEvent
>>> import threading
>>> import time
>>> smart_event = SmartEvent(alpha=threading.current_thread())
>>> def f1(in_smart_event):
...     try:
...         time.sleep(3)
...         in_smart_event.resume()
...     except RemoteThreadNotAlive as e:
...         print('mainline is not alive')
>>> f1_thread = threading.Thread(target=f1, args=(smart_event,)
>>> smart_event.register_thread(beta=f1_thread)
>>> f1_thread.start()
>>> try:
>>>     smart_event.wait()
>>> except RemoteThreadNotAlive:
>>>     print('Thread f1 is not alive')


The smart_event module contains:

    1) SmartEvent class with methods:

       a. get_code
       b. resume
       c. register_thread
       d. sync
       e. wait
       f. wait_until

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
    """SmartEvent exception for no-op register_thread request."""
    pass


class IncorrectThreadSpecified(SmartEventError):
    """SmartEvent exception for incorrect thread specification."""
    pass


class DuplicateThreadSpecified(SmartEventError):
    """SmartEvent exception for duplicate thread specification."""
    pass


class ThreadAlreadyRegistered(SmartEventError):
    """SmartEvent exception for thread already registered."""
    pass


class BothAlphaBetaNotRegistered(SmartEventError):
    """SmartEvent exception for alpha or beta thread not registered."""
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
              'ThreadsReady RemoteWaiting RemoteResume')


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
            alpha: one of the two threads that are to be coordinated.
            beta: one of the two threads that are to be coordinated.

        """
        self._wait_check_lock = threading.Lock()
        self._both_threads_registered = False
        self._sync_detected = False
        self._deadlock_detected = False
        self.sync_cleanup = False
        self.debug_logging_enabled = logger.isEnabledFor(logging.DEBUG)

        self.alpha = SmartEvent.ThreadEvent(name='alpha',
                                            event=threading.Event())
        self.beta = SmartEvent.ThreadEvent(name='beta',
                                           event=threading.Event())

        if alpha or beta:
            self.register_thread(alpha=alpha, beta=beta)

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
    # get_code
    ###########################################################################
    def get_code(self) -> Any:
        """Get code from last ``resume()``.

        Returns:
            The code provided by the thread that did the ``resume()`` event

        :Example: instantiate SmartEvent and ``resume()`` with a code

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> import threading
        >>> def f1(smart_event: SmartEvent) -> None:
        ...     print('f1 about to wait')
        ...     smart_event.wait()
        ...     print('f1 back from wait, about to retrieve code')
        ...     print(f'code = {smart_event.get_code()}')

        >>> a_smart_event = SmartEvent(alpha=threading.current_thread())
        >>> f1_thread = threading.Thread(target=f1, args=(a_smart_event,))
        >>> a_smart_event.register_thread(beta=f1_thread)
        >>> f1_thread.start()
        >>> a_smart_event.wait_until(WUCond.ThreadsReady)
        >>> a_smart_event.wait_until(WUCond.RemoteWaiting)
        >>> print('mainline about to resume f1')
        >>> a_smart_event.resume(code=42)
        >>> f1_thread.join()
        f1 about to wait
        mainline about to resume f1
        f1 back from wait, about to retrieve code
        code = 42

        """
        current, _ = self._get_current_remote()
        return current.code

    ###########################################################################
    # register_thread
    ###########################################################################
    def register_thread(self, *,
                   alpha: Optional[threading.Thread] = None,
                   beta: Optional[threading.Thread] = None
                   ) -> None:
        """Register alpha and/or beta thread.

        Args:
            alpha: one of the two threads that are to be coordinated.
            beta: one of the two threads that are to be coordinated.

        Raises:
            NeitherAlphaNorBetaSpecified:  At least one of **alpha** or
                                             **beta** must be specified for
                                             a ``register_threads()`` request.
            IncorrectThreadSpecified: The **alpha** and **beta** arguments must
                                        be of type *threading.Thread*.
            DuplicateThreadSpecified: The **alpha** and **beta** arguments
                                        must be for separate and distinct
                                        objects of type **threading.Thread**.
            ThreadAlreadyRegistered: The ``register_thread()`` method detected
                                       that the specified thread has already
                                       been registered to either a different
                                       or the same input thread.

        Notes:
            1) The alpha and beta threads can be registered when the
               SmartEvent is instantiated or via the ``register_thread()``
               method. Any combination may be used, but once registered,
               neither thread can be registered again, including its original
               value.

        :Example: instantiate a SmartEvent and registered the alpha thread

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> smart_event = SmartEvent()
        >>> smart_event.register_thread(alpha=threading.current_thread())

        """
        if not (alpha or beta):
            logger.debug('raising NeitherAlphaNorBetaSpecified')
            raise NeitherAlphaNorBetaSpecified(
                'One of alpha or beta must be specified for a '
                '``register_thread()`` request. '
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
            logger.debug('raising ThreadAlreadyRegistered')
            raise ThreadAlreadyRegistered(
                'The ``register_thread()`` method detected that the specified '
                'thread has already been registered to either a different or '
                'the same input thread. '
                f'Call sequence: {get_formatted_call_sequence()}')

        if alpha:
            self.alpha.thread = alpha
        if beta:
            self.beta.thread = beta

        if self.alpha.thread and self.beta.thread:
            self._both_threads_registered = True

    ###########################################################################
    # resume
    ###########################################################################
    def resume(self, *,
               log_msg: Optional[str] = None,
               timeout: Optional[Union[int, float]] = None,
               code: Optional[Any] = None) -> bool:
        """Resume a waiting (or soon to wait) thread.

        Args:
            log_msg: log msg to log
            timeout: number of seconds to allow for ``resume()`` to complete
            code: code that waiter can retrieve with ``get_code()``

        Returns:
            * ``True`` if *timeout* was not specified, or if it was specified
              and the ``resume()`` request completed within the specified
              number of seconds.
            * ``False`` if *timeout* was specified and the ``resume()``
              request did not complete within the specified number of
              seconds.

        Notes:

            1) A ``resume()`` request can be done on an event that is not yet
               being waited upon. This is referred as a **pre-resume**. The
               remote thread doing a ``wait()`` request on a **pre-resume**
               event will be completed immediatly.
            2) If the ``resume()`` request sees that the event has already
               been resumed, it will loop and wait for the event to be cleared
               under the assumption that the event was previously
               **pre-resumed** and a wait is imminent. The ``wait()`` will
               clear the event and the ``resume()`` request will simply resume
               it again as a **pre-resume**.
            3) If one thread makes a ``resume()`` request and the other thread
               becomes not alive, the ``resume()`` request raises a
               **RemoteThreadNotAlive** error.

        :Example: instantiate SmartEvent and ``resume()`` event that function
                    waits on

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> import threading
        >>> def f1(smart_event: SmartEvent) -> None:
        ...     smart_event.wait()

        >>> a_smart_event = SmartEvent(alpha=threading.current_thread())
        >>> f1_thread = threading.Thread(target=f1, args=(a_smart_event,))
        >>> a_smart_event.register_thread(beta=f1_thread)
        >>> f1_thread.start()
        >>> a_smart_event..wait_until(WUCond.ThreadsReady)
        >>> a_smart_event.resume()
        >>> f1_thread.join()

        """
        current, remote = self._get_current_remote()
        code_msg = f' with code: {code} ' if code else ' '

        # if caller specified a log message to issue
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            logger.debug(f'resume() entered{code_msg}'
                         f'{caller_info} {log_msg}')

        start_time = time.time()
        while True:
            with self._wait_check_lock:
                self._check_remote(current, remote)
                ###############################################################
                # Cases where we loop until remote is ready:
                # 1) Remote waiting and event already resumed. This is a case
                #    where the remote was previously resumed and has not yet
                #    been given control to exit the wait. If and when that
                #    happens, this resume will complete as a pre-resume.
                # 2) Remote waiting and deadlock. The remote was flagged as
                #    being in a deadlock and has not been given control to
                #    raise the WaitDeadlockDetected error. The remote could
                #    recover, in which case this resume will complete,
                #    or the thread could become inactive, in which case
                #    resume will see that and raise (via _check_remote
                #    method) the RemoteThreadNotAlive error.
                # 3) Remote not waiting and event resumed. This case
                #    indicates that a resume was previously done ahead of the
                #    wait as a pre-resume. In that case an eventual wait is
                #    expected to be requested by the remote thread to clear
                #    the flag at which time this resume will succeed in doing a
                #    pre-resume.
                ###############################################################

                ###############################################################
                # Cases where we do the resume:
                # 1) Remote is waiting, event is not resumed, and neither
                #    deadlock nor conflict flags are True. This is the most
                #    expected case in a normally running system where the
                #    remote put something in action and is now waiting on a
                #    response (via the resume) that the action is complete.
                # 2) Remote is not waiting, not sync_wait, and event not
                #    resumed. This is a case where we will do a pre-resume and
                #    the remote is expected to do the wait momentarily.
                # 3) Remote is not waiting, but is sync waiting, and event not
                #    resumed. This case is identical to case 2 from a resume
                #    perspective since the sync_wait does not interfere with
                #    the event that the resume operates on. So, we will so
                #    a pre-resume and the expectation in that this
                #    thread will then complete the sync with the remote
                #    who will next do a wait against the pre-resume. The
                #    vertical time line for both sides could be represented as
                #    such:
                #
                #        Current Thread                   Remote Thread
                #                                           sync
                #              resume
                #              sync
                #                                           wait
                ###############################################################
                if not (current.event.is_set()
                        or remote.deadlock
                        or (remote.conflict and remote.waiting)):
                    if code:  # if caller specified a code for remote thread
                        remote.code = code
                    current.event.set()  # wake remote thread
                    ret_code = True
                    break

                if timeout and (timeout < (time.time() - start_time)):
                    logger.debug(f'{current.name} timeout of a resume() '
                                 'request with current.event.is_set() = '
                                 f'{current.event.is_set()} and '
                                 f'remote.deadlock = '
                                 f'{remote.deadlock}')
                    ret_code = False
                    break

            time.sleep(0.2)

        # if caller specified a log message to issue
        if log_msg and self.debug_logging_enabled:
            logger.debug(f'resume() exiting with ret_code {ret_code} '
                         f'{caller_info} {log_msg}')
        return ret_code

    ###########################################################################
    # sync
    ###########################################################################
    def sync(self, *,
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None) -> bool:
        """Sync up with the remote thread via a matching sync request.

        A ``sync()`` request made by the current thread waits until the remote
        thread makes a matching ``sync()`` request at which point both
        ``sync()`` requests are completed and control returned.

        Args:
            log_msg: log msg to log
            timeout: number of seconds to allow for sync to happen

        Returns:
            * ``True`` if **timeout** was not specified, or if it was
              specified and the ``sync()`` request completed within the
              specified number of seconds.
            * ``False`` if **timeout** was specified and the ``sync()``
              request did not complete within the specified number of
              seconds.

        Raises:
            ConflictDeadlockDetected: A ``sync()`` request was made by one
                                        thread and a ``wait()`` request was
                                        made by the other thread.

        Notes:
            1) If one thread makes a ``sync()`` request without **timeout**
               specified, and the other thread makes a ``wait()`` request to
               an event that was not **pre-resumed**, also without **timeout**
               specified, then both threads will recognize and raise a
               **ConflictDeadlockDetected** error. This is needed since
               neither the ``sync()`` request nor the ``wait()`` request has
               any chance of completing. The ``sync()`` request is waiting for
               a matching ``sync()`` request and the ``wait()`` request is
               waiting for a matching ``resume()`` request.
            2) If one thread makes a ``sync()`` request and the other thread
               becomes not alive, the ``sync()`` request raises a
               **RemoteThreadNotAlive** error.

        :Example: instantiate a SmartEvent and sync the threads

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> import threading
        >>> def f1(smart_event: SmartEvent) -> None:
        ...     smart_event.sync()

        >>> smart_event = SmartEvent(alpha=threading.current_thread())
        >>> f1_thread = threading.Thread(target=f1, args=(smart_event,))
        >>> smart_event.register_thread(beta=f1_thread)
        >>> f1_thread.start()
        >>> smart_event.sync()
        >>> f1_thread.join()

        """
        current, remote = self._get_current_remote()
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            logger.debug(f'sync() entered {caller_info} {log_msg}')

        start_time = time.time()
        current.sync_wait = True

        #######################################################################
        # States:
        # remote.waiting is normal wait. Raise Conflict if not timeout on
        # either side.
        #
        # not remote sync_wait and sync_cleanup is remote in cleanup waiting
        # for us to set sync_cleanup to False
        #
        # remote.sync_wait and not sync_cleanup is remote waiting to see us
        # in sync_wait
        #
        # remote.sync_wait and sync_cleanup means we saw remote in sync_wait
        # and flipped sync_cleanup to True
        #
        #######################################################################
        ret_code = True
        while True:
            with self._wait_check_lock:
                if not (current.conflict or remote.conflict):
                    if current.sync_wait:  # we are phase 1
                        if remote.sync_wait:  # remote in phase 1
                            # we now go to phase 2
                            current.sync_wait = False
                            self.sync_cleanup = True
                        elif self.sync_cleanup:  # remote in phase 2
                            current.sync_wait = False
                            self.sync_cleanup = False
                            break
                    else:  # we are phase 2
                        if not self.sync_cleanup:  # remote exited phase 2
                            break

                if not (current.timeout_specified
                        or remote.timeout_specified
                        or current.conflict):
                    if (remote.waiting
                        and not (current.event.is_set()
                                 or remote.deadlock
                                 or remote.conflict)):
                        remote.conflict = True
                        current.conflict = True

                if current.conflict:
                    logger.debug(
                        f'{current.name} raising '
                        'ConflictDeadlockDetected. '
                        f'remote.waiting = {remote.waiting}, '
                        f'current.event.is_set() = {current.event.is_set()}, '
                        f'remote.deadlock = {remote.deadlock}, '
                        f'remote.conflict = {remote.conflict}, '
                        f'remote.timeout_specified = '
                        f'{remote.timeout_specified}, '
                        f'current.timeout_specified = '
                        f'{current.timeout_specified}')
                    current.sync_wait = False
                    current.conflict = False
                    raise ConflictDeadlockDetected(
                        'A sync request was made by thread '
                        f'{current.name} and a wait request was '
                        f'made by thread  {remote.name}.')

                self._check_remote(current, remote)

                if timeout and (timeout < (time.time() - start_time)):
                    logger.debug(f'{current.name} timeout of a sync '
                                 'request.')
                    current.sync_wait = False
                    ret_code = False
                    break

            time.sleep(0.1)

        if log_msg and self.debug_logging_enabled:
            logger.debug(f'sync() exiting with ret_code {ret_code} '
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
            * ``True`` if *timeout* was not specified, or if it was specified
              and the ``wait()`` request completed within the specified
              number of seconds.
            * ``False`` if *timeout* was specified and the ``wait()``
              request did not complete within the specified number of
              seconds.

        Raises:
            WaitDeadlockDetected: Both threads are deadlocked, each waiting
                                    on the other to ``resume()`` their event.
            ConflictDeadlockDetected: A ``sync()`` request was made by
                                        the current thread but the
                                        but the remote thread
                                        detected deadlock instead
                                        which indicates that the
                                        remote thread did not make a
                                        matching ``sync()`` request.

        Notes:
            1) If one thread makes a ``sync()`` request without **timeout**
               specified, and the other thread makes a ``wait()`` request to
               an event that was not **pre-resumed**, also without **timeout**
               specified, then both threads will recognize and raise a
               **ConflictDeadlockDetected** error. This is needed since
               neither the ``sync()`` request nor the ``wait()`` request has
               any chance of completing. The ``sync()`` request is waiting for
               a matching ``sync()`` request and the ``wait()`` request is
               waiting for a matching ``resume()`` request.
            2) If one thread makes a ``wait()`` request to an event that
               has not been **pre-resumed**, and without **timeout**
               specified, and the other thread makes a ``wait()`` request to
               an event that was not **pre-resumed**, also without **timeout**
               specified, then both threads will recognize and raise a
               **WaitDeadlockDetected** error. This is needed since neither
               ``wait()`` request has any chance of completing as each
               ``wait()`` request is waiting for a matching ``resume()``
               request.
            3) If one thread makes a ``wait()`` request and the other thread
               becomes not alive, the ``wait()`` request raises a
               **RemoteThreadNotAlive** error.

        :Example: instantiate a SmartEvent and ``wait()`` for function to
                  ``resume()``

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> import threading
        >>> def f1(smart_event: SmartEvent) -> None:
        ...     time.sleep(1)
        ...     smart_event.resume()

        >>> a_smart_event = SmartEvent(alpha=threading.current_thread())
        >>> f1_thread = threading.Thread(target=f1, args=(a_smart_event,))
        >>> a_smart_event.register_thread(beta=f1_thread)
        >>> f1_thread.start()
        >>> a_smart_event.wait_until(WUCond.ThreadsReady)
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
            logger.debug(f'wait() entered {caller_info} {log_msg}')

        current.waiting = True
        start_time = time.time()

        while True:
            ret_code = remote.event.wait(timeout=t_out)

            # We need to do the following checks while locked to prevent
            # either thread from setting the other thread's flags AFTER
            # the other thread has already detected those
            # conditions, set the flags, left, and is back with a new
            # request.
            with self._wait_check_lock:
                # Now that we have the lock we need to determine whether
                # we were resumed between the call and getting the lock
                if ret_code or remote.event.is_set():
                    current.waiting = False
                    remote.event.clear()  # be ready for next wait
                    ret_code = True
                    break

                # Check for error conditions first before checking
                # whether the remote is alive. If the remote detects a
                # deadlock or conflict issue, it will set the current
                # sides bit and then raise an error and will likely be
                # gone when we check. We want to raise the same error on
                # this side.

                # current.deadlock is set only by the remote. So, if
                # current.deadlock is True, then remote has already
                # detected the deadlock, set our flag, raised
                # the deadlock on its side, and is now possibly in a new
                # wait. If current.deadlock if False, and remote is waiting
                # and is not resumed then it will not be getting resumed by us
                # since we are also waiting. So, we set remote.deadlock
                # to tell it, and then we raise the error on our side.
                # But, we don't do this if the remote.deadlock is
                # already on as that suggests that we already told
                # remote and raised the error, which implies that we are
                # in a new wait and the remote has not yet woken up to
                # deal with the earlier deadlock. We can simply ignore
                # it for now.

                if not (current.timeout_specified
                        or remote.timeout_specified
                        or current.deadlock
                        or current.conflict):
                    if (remote.sync_wait
                            and not (self.sync_cleanup
                                     or remote.conflict)):
                        remote.conflict = True
                        current.conflict = True
                        logger.debug(f'{current.name} detected conflict')
                    elif (remote.waiting
                            and not (current.event.is_set()
                                     or remote.deadlock
                                     or remote.conflict)):
                        remote.deadlock = True
                        current.deadlock = True
                        logger.debug(f'{current.name} detected deadlock')

                if current.conflict:
                    current.waiting = False
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

                if current.deadlock:
                    current.waiting = False
                    current.deadlock = False
                    logger.debug(f'{current.name} raising '
                                 'WaitDeadlockDetected')
                    raise WaitDeadlockDetected(
                        'Both threads are deadlocked, each waiting on '
                        'the other to resume their event.')

                self._check_remote(current, remote)

                if timeout and (timeout < (time.time() - start_time)):
                    logger.debug(f'{current.name} timeout of a wait '
                                 'request with current.waiting = '
                                 f'{current.waiting} and '
                                 f'current.sync_wait = {current.sync_wait}')
                    current.waiting = False
                    ret_code = False
                    break

        if log_msg and self.debug_logging_enabled:
            logger.debug(f'wait() exiting with ret_code {ret_code} '
                         f'{caller_info} {log_msg}')

        return ret_code

    ###########################################################################
    # wait_until
    ###########################################################################
    def wait_until(self,
                   cond: WUCond,
                   timeout: Optional[Union[int, float]] = None
                   ) -> None:
        """Wait until a specific condition is met.

        Args:
            cond: specifies to either wait for:
                1) both threads to be registered and alive
                   (WUCond.ThreadsReady)
                2) the remote to call ``wait()`` (WUCond.RemoteWaiting)
                3) the remote to call ``resume()`` (WUCond.RemoteWaiting)
            timeout: number of seconds to allow for wait_until to succeed

        Raises:
            WaitUntilTimeout: The wait_until method timed out.

        :Example: instantiate SmartEvent and wait for ready

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> import threading
        >>> def f1(smart_event: SmartEvent) -> None:
        ...     smart_event.register_thread(beta=threading.current_thread())
        ...     smart_event.wait()

        >>> a_smart_event = SmartEvent(alpha=threading.current_thread())
        >>> f1_thread = threading.Thread(target=f1, args=(a_smart_event,))
        >>> f1_thread.start()
        >>> a_smart_event.wait_until(WUCond.ThreadsReady)
        >>> a_smart_event.resume()
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
            while not (self._both_threads_registered
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
                # make sure we are waiting for a new resume, meaning that
                # the event is not resumed and we are not doing a sync_wait
                # which may indicate the thread did not get control
                # yet to return from a previous resume or sync
                if (remote.waiting
                        and not current.event.is_set()
                        and not remote.sync_wait):
                    return

                self._check_remote(current, remote)

                if timeout and (timeout < (time.time() - start_time)):
                    logger.debug(f'{current.name} raising WaitUntilTimeout')
                    raise WaitUntilTimeout(
                        'The wait_until method timed out. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                time.sleep(t_out)

        #######################################################################
        # Handle RemoteResume
        #######################################################################
        elif cond == WUCond.RemoteResume:
            current, remote = self._get_current_remote()
            while not remote.event.is_set():

                self._check_remote(current, remote)

                if timeout and (timeout < (time.time() - start_time)):
                    logger.debug(f'{current.name} raising WaitUntilTimeout')
                    raise WaitUntilTimeout(
                        'The wait_until method timed out. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                time.sleep(t_out)

    ###########################################################################
    # _check_remote
    ###########################################################################
    def _check_remote(self,
                      current: ThreadEvent,
                      remote: ThreadEvent) -> None:
        """Check the remote flags for consitency and whether remote is alive.

        Args:
            current: contains flags for this thread
            remote: contains flags for remote thread

        Raises:
            InconsistentFlagSettings: The remote ThreadEvent flag settings
                                        are not valid.
            RemoteThreadNotAlive: The alpha or beta thread is not alive

        """
        # error cases for remote flags
        # 1) both waiting and sync_wait
        # 2) waiting False and deadlock or conflict are True
        # 3) sync_wait False and deadlock or conflict are True
        # 4) sync_wait and deadlock
        # 5) deadlock True and conflict True
        if ((remote.deadlock and remote.conflict)
                or (remote.waiting and remote.sync_wait)
                or ((remote.deadlock or remote.conflict)
                    and not (remote.waiting or remote.sync_wait))):
            logger.debug(f'{current.name} raising '
                         'InconsistentFlagSettings. '
                         f'waiting: {remote.waiting}, '
                         f'sync_wait: {remote.sync_wait}, '
                         f'deadlock: {remote.deadlock}, '
                         f'conflict: {remote.conflict}, ')
            raise InconsistentFlagSettings(
                f'Thread {current.name} detected remote {remote.name} '
                f'SmartEvent flag settings are not valid.')

        if not remote.thread.is_alive():
            logger.debug(f'{current.name} raising '
                         'RemoteThreadNotAlive.'
                         f'Call sequence: {get_formatted_call_sequence()}')
            raise RemoteThreadNotAlive(
                f'The current thread has detected that {remote.name} '
                'thread is not alive.')

    ###########################################################################
    # _get_current_remote
    ###########################################################################
    def _get_current_remote(self) -> Tuple[ThreadEvent, ThreadEvent]:
        """Get the current and remote ThreadEvent objects.

        Raises:
            BothAlphaBetaNotRegistered: Both threads must be registered before
                                          any SmartEvent services can be
                                          called.
            DetectedOpFromForeignThread: Any SmartEvent services must be
                                           called from  either the alpha or
                                           the beta thread registered at time
                                           of instantiation or via the
                                           ``register_thread()`` method.

        Returns:
            The current and remote ThreadEvent objects

        """
        if not self._both_threads_registered:
            logger.debug('raising BothAlphaBetaNotRegistered')
            raise BothAlphaBetaNotRegistered(
                'Both threads must be registered before any '
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
                'Any SmartEvent services must be called from  either the '
                'alpha or the beta thread registered at time of '
                'instantiation or via the ``register_thread()`` method. '
                f'Call sequence: {get_formatted_call_sequence(1,2)}')
