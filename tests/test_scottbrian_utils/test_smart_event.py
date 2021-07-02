"""test_smart_event.py module."""

from enum import Enum
import time
import math
import pytest
from typing import Any, cast, List
import threading
import re
import copy
import traceback
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.smart_event import (SmartEvent,
                                          WUCond,
                                          NeitherAlphaNorBetaSpecified,
                                          IncorrectThreadSpecified,
                                          DuplicateThreadSpecified,
                                          ThreadAlreadySet,
                                          BothAlphaBetaNotSet,
                                          DetectedOpFromForeignThread,
                                          RemoteThreadNotAlive,
                                          WaitUntilTimeout,
                                          WaitDeadlockDetected,
                                          ConflictDeadlockDetected,
                                          InconsistentFlagSettings)

import logging

logger = logging.getLogger(__name__)
logger.debug('about to start the tests')


###############################################################################
# SmartEvent test exceptions
###############################################################################
class ErrorTstSmartEvent(Exception):
    """Base class for exception in this module."""
    pass


class IncorrectActionSpecified(ErrorTstSmartEvent):
    """IncorrectActionSpecified exception class."""
    pass


class UnrecognizedMessageType(ErrorTstSmartEvent):
    """UnrecognizedMessageType exception class."""
    pass


class UnrecognizedCmd(ErrorTstSmartEvent):
    """UnrecognizedCmd exception class."""
    pass


###############################################################################
# Cmd Constants
###############################################################################
Cmd = Enum('Cmd', 'Wait Set Exit')

###############################################################################
# Action
###############################################################################
Action = Enum('Action',
              'MainWait MainSet '
              'ThreadWait ThreadSet ')

###############################################################################
# action_arg fixtures
###############################################################################
action_arg_list = [Action.MainWait, Action.MainSet,
                   Action.ThreadWait, Action.ThreadSet]


@pytest.fixture(params=action_arg_list)  # type: ignore
def action_arg1(request: Any) -> Any:
    """Using different reply messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


@pytest.fixture(params=action_arg_list)  # type: ignore
def action_arg2(request: Any) -> Any:
    """Using different reply messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


###############################################################################
# timeout_arg fixtures
###############################################################################
timeout_arg_list = [None, 'TO_False', 'TO_True']


@pytest.fixture(params=timeout_arg_list)  # type: ignore
def timeout_arg1(request: Any) -> Any:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


@pytest.fixture(params=timeout_arg_list)  # type: ignore
def timeout_arg2(request: Any) -> Any:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


###############################################################################
# code fixtures
###############################################################################
code_arg_list = [None, 42]


@pytest.fixture(params=code_arg_list)  # type: ignore
def code_arg1(request: Any) -> Any:
    """Using different codes.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=code_arg_list)  # type: ignore
def code_arg2(request: Any) -> Any:
    """Using different codes.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# log_msg fixtures
###############################################################################
log_msg_arg_list = [None, 'log msg1']


@pytest.fixture(params=log_msg_arg_list)  # type: ignore
def log_msg_arg1(request: Any) -> Any:
    """Using different log messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=log_msg_arg_list)  # type: ignore
def log_msg_arg2(request: Any) -> Any:
    """Using different log messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# TestSmartEventBasic class to test SmartEvent methods
###############################################################################
class TestSmartEventBasic:
    """Test class for SmartEvent basic tests."""

    ###########################################################################
    # repr for SmartEvent
    ###########################################################################
    def test_smart_event_repr(self,
                              thread_exc: "ThreadExc") -> None:
        """test event with code repr."""
        smart_event = SmartEvent()

        expected_repr_str = 'SmartEvent()'

        assert repr(smart_event) == expected_repr_str

        del smart_event

        smart_event2 = SmartEvent(alpha=threading.current_thread())

        alpha_repr = repr(smart_event2.alpha.thread)

        expected_repr_str = f'SmartEvent(alpha={alpha_repr})'

        assert repr(smart_event2) == expected_repr_str

        del smart_event2

        a_thread = threading.Thread()
        smart_event3 = SmartEvent(beta=a_thread)

        beta_repr = repr(smart_event3.beta.thread)

        expected_repr_str = f'SmartEvent(beta={beta_repr})'

        assert repr(smart_event3) == expected_repr_str

        del smart_event3

        def f1():
            pass

        def f2():
            pass

        a_thread1 = threading.Thread(target=f1)
        a_thread2 = threading.Thread(target=f2)
        smart_event4 = SmartEvent(alpha=a_thread1, beta=a_thread2)
        alpha_repr = repr(smart_event4.alpha.thread)
        beta_repr = repr(smart_event4.beta.thread)
        expected_repr_str = f'SmartEvent(alpha={alpha_repr}, beta={beta_repr})'

        assert repr(smart_event4) == expected_repr_str

    ###########################################################################
    # test_smart_event_set_thread_alpha_first
    ###########################################################################
    def test_smart_event_set_thread_alpha_first(self) -> None:
        """Test set_thread alpha first."""

        alpha_t = threading.current_thread()
        beta_t = threading.Thread()
        smart_event = SmartEvent()

        assert smart_event.alpha.thread is None
        assert smart_event.beta.thread is None
        assert smart_event._both_threads_set is False
        assert isinstance(smart_event.alpha.event, threading.Event)
        assert isinstance(smart_event.beta.event, threading.Event)
        assert smart_event.alpha.code is None
        assert smart_event.beta.code is None

        # not OK to set alpha and beta both to same thread
        with pytest.raises(DuplicateThreadSpecified):
            smart_event = SmartEvent(alpha=alpha_t, beta=alpha_t)

        # try wait, set, and wait_until without threads set
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event.wait()

        with pytest.raises(BothAlphaBetaNotSet):
            smart_event.set()

        with pytest.raises(BothAlphaBetaNotSet):
            smart_event.wait_until(WUCond.RemoteWaiting)

        with pytest.raises(IncorrectThreadSpecified):
            smart_event.set_thread(alpha=3)  # type: ignore
            
        with pytest.raises(IncorrectThreadSpecified):
            smart_event.set_thread(beta=3)  # type: ignore

        assert smart_event.alpha.thread is None
        assert smart_event.beta.thread is None
        assert smart_event._both_threads_set is False

        # set alpha

        # not OK to call set_threads without either alpha and beta
        with pytest.raises(NeitherAlphaNorBetaSpecified):
            smart_event.set_thread()

        smart_event.set_thread(alpha=alpha_t)
        assert smart_event.alpha.thread is alpha_t
        assert smart_event.beta.thread is None
        assert smart_event._both_threads_set is False

        # try wait and set without threads set
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event.wait()

        with pytest.raises(BothAlphaBetaNotSet):
            smart_event.set()

        with pytest.raises(BothAlphaBetaNotSet):
            smart_event.wait_until(WUCond.RemoteWaiting)

        # not OK to set alpha once set, even with same thread
        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(alpha=beta_t)
        assert smart_event.alpha.thread is alpha_t
        assert smart_event.beta.thread is None
        assert smart_event._both_threads_set is False

        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(alpha=alpha_t)
        assert smart_event.alpha.thread is alpha_t
        assert smart_event.beta.thread is None
        assert smart_event._both_threads_set is False

        # not OK to set beta to same thread as alpha
        with pytest.raises(DuplicateThreadSpecified):
            smart_event.set_thread(beta=alpha_t)
        assert smart_event.alpha.thread is alpha_t
        assert smart_event.beta.thread is None
        assert smart_event._both_threads_set is False

        smart_event.set_thread(beta=beta_t)

        assert smart_event.alpha.thread is alpha_t
        assert smart_event.beta.thread is beta_t
        assert smart_event._both_threads_set

        # not OK to set same beta thread
        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(beta=beta_t)

        assert smart_event.alpha.thread is alpha_t
        assert smart_event.beta.thread is beta_t
        assert smart_event._both_threads_set

        # not OK to set different beta thread
        beta2 = threading.Thread()
        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(beta=beta2)

        assert smart_event.alpha.thread is alpha_t
        assert smart_event.beta.thread is beta_t
        assert smart_event._both_threads_set
        assert isinstance(smart_event.alpha.event, threading.Event)
        assert isinstance(smart_event.beta.event, threading.Event)
        assert smart_event.alpha.code is None
        assert smart_event.beta.code is None

        del smart_event

        # try a foreign op
        alpha_t2 = threading.Thread()
        smart_event2 = SmartEvent(alpha=alpha_t2, beta=beta2)

        assert smart_event2.alpha.thread is alpha_t2
        assert smart_event2.beta.thread is beta2
        assert smart_event2._both_threads_set
        assert isinstance(smart_event2.alpha.event, threading.Event)
        assert isinstance(smart_event2.beta.event, threading.Event)
        assert smart_event2.alpha.code is None
        assert smart_event2.beta.code is None

        with pytest.raises(DetectedOpFromForeignThread):
            smart_event2.wait()

        with pytest.raises(DetectedOpFromForeignThread):
            smart_event2.set(code=42)

        with pytest.raises(DetectedOpFromForeignThread):
            smart_event2.get_code()

        with pytest.raises(DetectedOpFromForeignThread):
            smart_event2.wait_until(WUCond.RemoteWaiting)

        assert smart_event2.alpha.thread is alpha_t2
        assert smart_event2.beta.thread is beta2
        assert smart_event2._both_threads_set
        assert isinstance(smart_event2.alpha.event, threading.Event)
        assert isinstance(smart_event2.beta.event, threading.Event)
        assert smart_event2.alpha.code is None
        assert smart_event2.beta.code is None

    ###########################################################################
    # test_smart_event_set_thread_beta_first
    ###########################################################################
    def test_smart_event_set_thread_beta_first(self) -> None:
        """Test set_thread beta first."""

        alpha_t = threading.current_thread()
        beta_t = threading.Thread()
        smart_event = SmartEvent()

        assert smart_event.alpha.thread is None
        assert smart_event.beta.thread is None
        assert smart_event._both_threads_set is False
        assert isinstance(smart_event.alpha.event, threading.Event)
        assert isinstance(smart_event.beta.event, threading.Event)
        assert smart_event.alpha.code is None
        assert smart_event.beta.code is None

        # try wait, set, and wait_until without threads set
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event.wait()

        with pytest.raises(BothAlphaBetaNotSet):
            smart_event.set()

        with pytest.raises(BothAlphaBetaNotSet):
            smart_event.wait_until(WUCond.RemoteWaiting)

        with pytest.raises(IncorrectThreadSpecified):
            smart_event.set_thread(alpha=3)

        with pytest.raises(IncorrectThreadSpecified):
            smart_event.set_thread(beta=3)

        assert smart_event.alpha.thread is None
        assert smart_event.beta.thread is None
        assert not smart_event._both_threads_set

        # set beta
        smart_event.set_thread(beta=beta_t)
        assert smart_event.alpha.thread is None
        assert smart_event.beta.thread is beta_t
        assert not smart_event._both_threads_set

        # not OK to set beta once set, even with same thread
        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(beta=alpha_t)
        assert smart_event.alpha.thread is None
        assert smart_event.beta.thread is beta_t
        assert not smart_event._both_threads_set

        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(beta=beta_t)
        assert smart_event.alpha.thread is None
        assert smart_event.beta.thread is beta_t
        assert not smart_event._both_threads_set

        # not OK to set alpha to same thread as beta
        with pytest.raises(DuplicateThreadSpecified):
            smart_event.set_thread(alpha=beta_t)
        assert smart_event.alpha.thread is None
        assert smart_event.beta.thread is beta_t
        assert not smart_event._both_threads_set

        # try wait, set, and wait_until without threads set
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event.wait()

        with pytest.raises(BothAlphaBetaNotSet):
            smart_event.set()

        with pytest.raises(BothAlphaBetaNotSet):
            smart_event.wait_until(WUCond.RemoteWaiting)

        smart_event.set_thread(alpha=alpha_t)

        assert smart_event.alpha.thread is alpha_t
        assert smart_event.beta.thread is beta_t
        assert smart_event._both_threads_set

        # not OK to set same alpha thread
        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(alpha=alpha_t)

        assert smart_event.alpha.thread is alpha_t
        assert smart_event.beta.thread is beta_t
        assert smart_event._both_threads_set

        # not OK to set different alpha thread
        alpha2 = threading.Thread()
        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(alpha=alpha2)

        assert smart_event.alpha.thread is alpha_t
        assert smart_event.beta.thread is beta_t
        assert smart_event._both_threads_set
        assert isinstance(smart_event.alpha.event, threading.Event)
        assert isinstance(smart_event.beta.event, threading.Event)
        assert smart_event.alpha.code is None
        assert smart_event.beta.code is None

    ###########################################################################
    # test_smart_event_set_threads_instantiate
    ###########################################################################
    def test_smart_event_set_threads_instantiate(self) -> None:
        """Test set_thread during instantiation."""

        alpha_t = threading.current_thread()
        beta_t = threading.Thread()

        smart_e1 = SmartEvent(alpha=alpha_t, beta=beta_t)
        assert smart_e1.alpha.thread is alpha_t
        assert smart_e1.beta.thread is beta_t
        assert smart_e1._both_threads_set
        assert isinstance(smart_e1.alpha.event, threading.Event)
        assert isinstance(smart_e1.beta.event, threading.Event)
        assert smart_e1.alpha.code is None
        assert smart_e1.beta.code is None

        del smart_e1

        smart_e2 = SmartEvent(alpha=alpha_t)
        assert smart_e2.alpha.thread is alpha_t
        assert smart_e2.beta.thread is None
        assert not smart_e2._both_threads_set
        assert isinstance(smart_e2.alpha.event, threading.Event)
        assert isinstance(smart_e2.beta.event, threading.Event)
        assert smart_e2.alpha.code is None
        assert smart_e2.beta.code is None

        del smart_e2

        smart_e3 = SmartEvent(beta=beta_t)
        assert smart_e3.alpha.thread is None
        assert smart_e3.beta.thread is beta_t
        assert not smart_e3._both_threads_set
        assert isinstance(smart_e3.alpha.event, threading.Event)
        assert isinstance(smart_e3.beta.event, threading.Event)
        assert smart_e3.alpha.code is None
        assert smart_e3.beta.code is None

        del smart_e3

        # not OK to set alpha with bad value
        with pytest.raises(IncorrectThreadSpecified):
            smart_e4 = SmartEvent(alpha=42)  # type: ignore

        # not OK to set beta with bad value
        with pytest.raises(IncorrectThreadSpecified):
            smart_e5 = SmartEvent(beta=17)  # type: ignore

        # not OK to set alpha and beta both to same thread
        with pytest.raises(DuplicateThreadSpecified):
            smart_e6 = SmartEvent(alpha=alpha_t, beta=alpha_t)

    ###########################################################################
    # test_smart_event_set_threads_f1
    ###########################################################################
    def test_smart_event_set_threads_f1(self) -> None:
        """Test set_thread with f1."""

        #######################################################################
        # mainline and f1 - mainline sets beta
        #######################################################################
        logger.debug('start test 1')
        current_thread = threading.current_thread()
        logger.debug(f'mainline current thread is {current_thread}')

        def f1(s_event, ml_thread):
            print('f1 entered')
            my_c_thread = threading.current_thread()
            assert s_event.alpha.thread is ml_thread
            assert s_event.alpha.thread is alpha_t
            assert s_event.beta.thread is my_c_thread
            assert s_event.beta.thread is threading.current_thread()

            s_event.sync(log_msg='        f1 beta sync point 1')

            logger.debug('        f1 beta about to enter cmd loop')
            while cmd[0] != Cmd.Exit:
                if cmd[0] == Cmd.Wait:
                    cmd[0] = 0
                    assert s_event.wait()

                elif cmd[0] == Cmd.Set:
                    cmd[0] = 0
                    with pytest.raises(WaitUntilTimeout):
                        s_event.wait_until(WUCond.RemoteWaiting, timeout=0.002)
                    with pytest.raises(WaitUntilTimeout):
                        s_event.wait_until(WUCond.RemoteWaiting, timeout=0.01)
                    with pytest.raises(WaitUntilTimeout):
                        s_event.wait_until(WUCond.RemoteWaiting, timeout=0.02)

                    s_event.sync(log_msg='        f1 beta sync point 2')

                    s_event.wait_until(WUCond.RemoteWaiting)
                    s_event.wait_until(WUCond.RemoteWaiting, timeout=0.001)
                    s_event.wait_until(WUCond.RemoteWaiting, timeout=0.01)
                    s_event.wait_until(WUCond.RemoteWaiting, timeout=0.02)
                    s_event.wait_until(WUCond.RemoteWaiting, timeout=-0.02)
                    s_event.wait_until(WUCond.RemoteWaiting, timeout=-1)
                    s_event.wait_until(WUCond.RemoteWaiting, timeout=0)

                    s_event.set()

                time.sleep(.1)

        def foreign1(s_event):
            logger.debug('foreign1 entered')
            with pytest.raises(WaitUntilTimeout):
                s_event.wait_until(WUCond.ThreadsReady, timeout=0.002)
            with pytest.raises(BothAlphaBetaNotSet):
                s_event.wait_until(WUCond.RemoteWaiting, timeout=0.02)

            cmd[0] = Cmd.Exit

            logger.debug('foreign1 about to wait_until ThreadsReady')
            s_event.wait_until(WUCond.ThreadsReady, timeout=10)

            with pytest.raises(DetectedOpFromForeignThread):
                s_event.wait_until(WUCond.RemoteWaiting, timeout=0.02)
            with pytest.raises(DetectedOpFromForeignThread):
                s_event.wait_until(WUCond.RemoteWaiting)
            with pytest.raises(DetectedOpFromForeignThread):
                s_event.wait()
            with pytest.raises(DetectedOpFromForeignThread):
                s_event.set()
            with pytest.raises(DetectedOpFromForeignThread):
                s_event.sync()

            logger.debug('foreign1 exiting')

        cmd = [0]
        alpha_t = threading.current_thread()
        smart_event1 = SmartEvent(alpha=threading.current_thread())

        logger.debug(f'id(smart_event1.alpha.event) = '
                     f'{id(smart_event1.alpha.event)}')
        logger.debug(f'id(smart_event1.beta.event) = '
                     f'{id(smart_event1.beta.event)}')

        my_foreign1_thread = threading.Thread(target=foreign1,
                                              args=(smart_event1,))
        my_foreign1_thread.start()
        my_f1_thread = threading.Thread(target=f1,
                                        args=(smart_event1,
                                              threading.current_thread()))
        with pytest.raises(WaitUntilTimeout):
            smart_event1.wait_until(WUCond.ThreadsReady, timeout=0.002)
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event1.wait_until(WUCond.RemoteWaiting, timeout=-0.002)
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event1.wait_until(WUCond.RemoteWaiting, timeout=0)
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event1.wait_until(WUCond.RemoteWaiting, timeout=0.002)
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event1.wait_until(WUCond.RemoteWaiting, timeout=0.2)
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event1.wait_until(WUCond.RemoteWaiting)

        while cmd[0] != Cmd.Exit:
            time.sleep(0.2)

        cmd[0] = 0

        logger.debug('mainline about to set beta thread')
        smart_event1.set_thread(beta=my_f1_thread)
        logger.debug('mainline back from setting beta thread')

        with pytest.raises(WaitUntilTimeout):
            smart_event1.wait_until(WUCond.ThreadsReady, timeout=0.005)

        my_f1_thread.start()
        smart_event1.wait_until(WUCond.ThreadsReady, timeout=1)

        smart_event1.sync(log_msg='mainline sync point 1')

        logger.debug('about to wait_until RemoteWaiting')
        with pytest.raises(WaitUntilTimeout):
            smart_event1.wait_until(WUCond.RemoteWaiting, timeout=0.002)
        with pytest.raises(WaitUntilTimeout):
            smart_event1.wait_until(WUCond.RemoteWaiting, timeout=0.01)
        with pytest.raises(WaitUntilTimeout):
            smart_event1.wait_until(WUCond.RemoteWaiting, timeout=0.02)
        with pytest.raises(WaitUntilTimeout):
            smart_event1.wait_until(WUCond.RemoteWaiting, timeout=1)

        cmd[0] = Cmd.Wait

        smart_event1.wait_until(WUCond.RemoteWaiting)
        smart_event1.wait_until(WUCond.RemoteWaiting, timeout=0.001)
        smart_event1.wait_until(WUCond.RemoteWaiting, timeout=0.01)
        smart_event1.wait_until(WUCond.RemoteWaiting, timeout=0.02)
        smart_event1.wait_until(WUCond.RemoteWaiting, timeout=-0.02)
        smart_event1.wait_until(WUCond.RemoteWaiting, timeout=-1)
        smart_event1.wait_until(WUCond.RemoteWaiting, timeout=0)

        smart_event1.set()

        cmd[0] = Cmd.Set
        smart_event1.sync(log_msg='mainline sync point 2')
        assert smart_event1.wait()

        cmd[0] = Cmd.Exit

        my_f1_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.set()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.wait_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.sync(log_msg='mainline sync point 3')

        assert smart_event1.alpha.thread is alpha_t
        assert smart_event1.beta.thread is my_f1_thread

        del smart_event1
        del my_f1_thread

        #######################################################################
        # mainline and f2 - f2 sets beta
        #######################################################################

        def f2(s_event, ml_thread):
            logger.debug('        f2 beta entered')
            my_c_thread = threading.current_thread()

            while cmd[0] != Cmd.Exit:
                time.sleep(0.2)
            cmd[0] = 0

            s_event.set_thread(beta=my_c_thread)
            assert s_event.alpha.thread is ml_thread
            assert s_event.alpha.thread is alpha_t
            assert s_event.beta.thread is my_c_thread
            assert s_event.beta.thread is threading.current_thread()

            s_event.sync(log_msg='        f2 thread sync point 1')

            with pytest.raises(WaitDeadlockDetected):
                s_event.wait()

            s_event.sync(log_msg='        f2 thread sync point 2')

            s_event.wait()  # clear the set that comes after the deadlock

            s_event.sync(log_msg='        f2 thread sync point 3')

            s_event.wait_until(WUCond.RemoteWaiting, timeout=2)
            with pytest.raises(WaitDeadlockDetected):
                s_event.wait()

            s_event.sync(log_msg='        f2 thread sync point 4')

            s_event.set()

        cmd[0] = 0
        smart_event2 = SmartEvent(alpha=threading.current_thread())

        with pytest.raises(WaitUntilTimeout):
            smart_event2.wait_until(WUCond.ThreadsReady, timeout=0.001)

        my_f2_thread = threading.Thread(target=f2, args=(smart_event2,
                                                         alpha_t))
        with pytest.raises(WaitUntilTimeout):
            smart_event2.wait_until(WUCond.ThreadsReady, timeout=0.01)

        with pytest.raises(BothAlphaBetaNotSet):
            smart_event2.wait_until(WUCond.RemoteWaiting, timeout=-0.002)
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event2.wait_until(WUCond.RemoteWaiting, timeout=0)
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event2.wait_until(WUCond.RemoteWaiting, timeout=0.002)
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event2.wait_until(WUCond.RemoteWaiting, timeout=0.2)
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event2.wait_until(WUCond.RemoteWaiting)

        my_f2_thread.start()

        with pytest.raises(WaitUntilTimeout):
            smart_event2.wait_until(WUCond.ThreadsReady, timeout=0.2)
        with pytest.raises(BothAlphaBetaNotSet):
            smart_event2.wait_until(WUCond.RemoteWaiting)

        cmd[0] = Cmd.Exit

        smart_event2.wait_until(WUCond.ThreadsReady)
        smart_event2.wait_until(WUCond.ThreadsReady, timeout=1)
        smart_event2.wait_until(WUCond.ThreadsReady, timeout=0)
        smart_event2.wait_until(WUCond.ThreadsReady, timeout=-1)
        smart_event2.wait_until(WUCond.ThreadsReady, timeout=-2)

        smart_event2.sync(log_msg='mainline sync point 1')

        with pytest.raises(WaitDeadlockDetected):
            smart_event2.wait()

        smart_event2.sync(log_msg='mainline sync point 2')

        smart_event2.set()

        smart_event2.sync(log_msg='mainline sync point 3')

        with pytest.raises(WaitDeadlockDetected):
            smart_event2.wait()

        smart_event2.sync(log_msg='mainline sync point 4')

        assert smart_event2.wait()  # clear set

        my_f2_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.set()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.sync(log_msg='mainline sync point 5')

        assert smart_event2.alpha.thread is alpha_t
        assert smart_event2.beta.thread is my_f2_thread

    ###########################################################################
    # test_smart_event_set_threads_thread_app
    ###########################################################################
    def test_smart_event_set_threads_thread_app(self) -> None:
        """Test set_thread with thread_app."""

        #######################################################################
        # mainline and ThreadApp - mainline sets beta
        #######################################################################
        class MyThread(threading.Thread):
            def __init__(self,
                         s_event: SmartEvent,
                         alpha_t1: threading.Thread):
                super().__init__()
                self.s_event = s_event
                self.alpha_t1 = alpha_t1

            def run(self):
                print('run started')
                assert self.s_event.alpha.thread is self.alpha_t1
                assert self.s_event.alpha.thread is alpha_t
                assert self.s_event.beta.thread is self
                my_run_thread = threading.current_thread()
                assert self.s_event.beta.thread is my_run_thread
                assert self.s_event.beta.thread is threading.current_thread()

                with pytest.raises(WaitUntilTimeout):
                    self.s_event.wait_until(WUCond.RemoteSet, timeout=0.009)
                time.sleep(2)
                self.s_event.wait_until(WUCond.RemoteSet, timeout=0.009)
                self.s_event.wait_until(WUCond.RemoteSet)
                assert self.s_event.wait()
                time.sleep(1)
                self.s_event.set()

        alpha_t = threading.current_thread()
        smart_event1 = SmartEvent(alpha=alpha_t)
        my_taa_thread = MyThread(smart_event1, alpha_t)
        smart_event1.set_thread(beta=my_taa_thread)
        my_taa_thread.start()
        
        smart_event1.wait_until(WUCond.ThreadsReady)
        time.sleep(1)
        smart_event1.set()

        with pytest.raises(WaitUntilTimeout):
            smart_event1.wait_until(WUCond.RemoteSet, timeout=0.009)
        time.sleep(2)
        smart_event1.wait_until(WUCond.RemoteSet, timeout=0.009)
        smart_event1.wait_until(WUCond.RemoteSet)
        assert smart_event1.wait()

        my_taa_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.set()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.wait_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.wait_until(WUCond.RemoteSet)

        assert smart_event1.alpha.thread is alpha_t
        assert smart_event1.beta.thread is my_taa_thread

        del smart_event1
        del my_taa_thread

        #######################################################################
        # mainline and ThreadApp - thread_app sets beta
        #######################################################################
        class MyThread2(threading.Thread):
            def __init__(self,
                         s_event: SmartEvent,
                         alpha_t1: threading.Thread):
                super().__init__()
                self.s_event = s_event
                self.s_event.set_thread(beta=self)
                self.alpha_t1 = alpha_t1

            def run(self):
                print('run started')
                assert self.s_event.alpha.thread is self.alpha_t1
                assert self.s_event.alpha.thread is alpha_t
                assert self.s_event.beta.thread is self
                my_run_thread = threading.current_thread()
                assert self.s_event.beta.thread is my_run_thread
                assert self.s_event.beta.thread is threading.current_thread()
                with pytest.raises(WaitDeadlockDetected):
                    self.s_event.wait()
                assert self.s_event.wait()
                self.s_event.wait_until(WUCond.ThreadsReady)
                self.s_event.wait_until(WUCond.RemoteWaiting)
                self.s_event.wait_until(WUCond.RemoteWaiting, timeout=2)

                self.s_event.set()

        smart_event2 = SmartEvent()
        smart_event2.set_thread(alpha=alpha_t)
        my_tab_thread = MyThread2(smart_event2, alpha_t)
        my_tab_thread.start()

        smart_event2.wait_until(WUCond.ThreadsReady)
        smart_event2.wait_until(WUCond.RemoteWaiting)
        with pytest.raises(WaitDeadlockDetected):
            smart_event2.wait()
        smart_event2.set()
        assert smart_event2.wait()

        my_tab_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.set()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.wait_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.wait_until(WUCond.RemoteSet)

        assert smart_event2.alpha.thread is alpha_t
        assert smart_event2.beta.thread is my_tab_thread

    ###########################################################################
    # test_smart_event_set_threads_thread_event_app
    ###########################################################################
    def test_smart_event_set_threads_thread_event_app(self) -> None:
        """Test set_thread with thread_event_app."""


        #######################################################################
        # mainline and ThreadEventApp - mainline sets alpha and beta
        #######################################################################
        class MyThreadEvent1(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self)
                self.alpha_t1 = alpha_t1
                with pytest.raises(WaitUntilTimeout):
                    self.wait_until(WUCond.ThreadsReady, timeout=0.1)

            def run(self):
                logger.debug('run started')
                self.wait_until(WUCond.ThreadsReady, timeout=0.1)
                assert self.alpha.thread is self.alpha_t1
                assert self.alpha.thread is alpha_t
                assert self.beta.thread is self
                my_run_thread = threading.current_thread()
                assert self.beta.thread is my_run_thread
                assert self.beta.thread is threading.current_thread()

                assert self.wait()
                self.wait_until(WUCond.RemoteWaiting, timeout=2)
                with pytest.raises(WaitDeadlockDetected):
                    self.wait()
                self.set()
                logger.debug('run exiting')

        alpha_t = threading.current_thread()

        my_te1_thread = MyThreadEvent1(alpha_t)
        with pytest.raises(WaitUntilTimeout):
            my_te1_thread.wait_until(WUCond.ThreadsReady, timeout=0.005)

        my_te1_thread.set_thread(alpha=alpha_t)
        with pytest.raises(WaitUntilTimeout):
            my_te1_thread.wait_until(WUCond.ThreadsReady, timeout=0.005)

        my_te1_thread.set_thread(beta=my_te1_thread)
        with pytest.raises(WaitUntilTimeout):
            my_te1_thread.wait_until(WUCond.ThreadsReady, timeout=0.005)

        assert my_te1_thread.alpha.thread is alpha_t
        assert my_te1_thread.beta.thread is my_te1_thread

        my_te1_thread.start()
        my_te1_thread.wait_until(WUCond.ThreadsReady)
        my_te1_thread.set()
        with pytest.raises(WaitDeadlockDetected):
            my_te1_thread.wait()

        assert my_te1_thread.wait()

        my_te1_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            my_te1_thread.set()

        with pytest.raises(RemoteThreadNotAlive):
            my_te1_thread.wait()

        with pytest.raises(RemoteThreadNotAlive):
            my_te1_thread.wait_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            my_te1_thread.wait_until(WUCond.RemoteSet)

        assert my_te1_thread.alpha.thread is alpha_t
        assert my_te1_thread.beta.thread is my_te1_thread

        del my_te1_thread

        #######################################################################
        # mainline and ThreadApp - mainline sets alpha thread_app sets beta
        #######################################################################
        class MyThreadEvent2(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, beta=self)
                self.alpha_t1 = alpha_t1
                with pytest.raises(WaitUntilTimeout):
                    self.wait_until(WUCond.ThreadsReady, timeout=0.005)

            def run(self):
                logger.debug('run started')
                self.wait_until(WUCond.ThreadsReady, timeout=0.005)
                assert self.alpha.thread is self.alpha_t1
                assert self.alpha.thread is alpha_t
                assert self.beta.thread is self
                my_run_thread = threading.current_thread()
                assert self.beta.thread is my_run_thread
                assert self.beta.thread is threading.current_thread()
                with pytest.raises(WaitDeadlockDetected):
                    self.wait()
                assert self.wait()
                self.set()
                logger.debug('run exiting')

        my_te2_thread = MyThreadEvent2(alpha_t)
        with pytest.raises(WaitUntilTimeout):
            my_te2_thread.wait_until(WUCond.ThreadsReady, timeout=0.005)
        my_te2_thread.set_thread(alpha=alpha_t)
        with pytest.raises(WaitUntilTimeout):
            my_te2_thread.wait_until(WUCond.ThreadsReady, timeout=0.005)
        my_te2_thread.start()

        my_te2_thread.wait_until(WUCond.ThreadsReady)

        my_te2_thread.wait_until(WUCond.RemoteWaiting, timeout=2)
        with pytest.raises(WaitDeadlockDetected):
            my_te2_thread.wait()

        my_te2_thread.set()
        assert my_te2_thread.wait()

        my_te2_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            my_te2_thread.set()

        with pytest.raises(RemoteThreadNotAlive):
            my_te2_thread.wait()

        with pytest.raises(RemoteThreadNotAlive):
            my_te2_thread.wait_until(WUCond.RemoteWaiting, timeout=2)

        with pytest.raises(RemoteThreadNotAlive):
            my_te2_thread.wait_until(WUCond.RemoteSet, timeout=2)

        assert my_te2_thread.alpha.thread is alpha_t
        assert my_te2_thread.beta.thread is my_te2_thread

        del my_te2_thread

        #######################################################################
        # mainline and ThreadApp - thread_app sets alpha and beta
        #######################################################################
        class MyThreadEvent3(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, alpha=alpha_t)
                with pytest.raises(WaitUntilTimeout):
                    self.wait_until(WUCond.ThreadsReady, timeout=0.005)
                self.set_thread(beta=self)
                with pytest.raises(WaitUntilTimeout):
                    self.wait_until(WUCond.ThreadsReady, timeout=0.001)
                self.alpha_t1 = alpha_t1

            def run(self):
                logger.debug('run started')
                self.wait_until(WUCond.ThreadsReady, timeout=0.001)
                assert self.alpha.thread is self.alpha_t1
                assert self.alpha.thread is alpha_t
                assert self.beta.thread is self
                my_run_thread = threading.current_thread()
                assert self.beta.thread is my_run_thread
                assert self.beta.thread is threading.current_thread()

                self.wait_until(WUCond.RemoteSet, timeout=2)
                assert self.wait()
                self.wait_until(WUCond.RemoteWaiting, timeout=2)
                with pytest.raises(WaitDeadlockDetected):
                    self.wait()
                self.set()
                logger.debug('run exiting')

        my_te3_thread = MyThreadEvent3(alpha_t)
        with pytest.raises(WaitUntilTimeout):
            my_te3_thread.wait_until(WUCond.ThreadsReady, timeout=0.005)
        my_te3_thread.start()

        my_te3_thread.wait_until(WUCond.ThreadsReady, timeout=2)
        my_te3_thread.set()
        with pytest.raises(WaitDeadlockDetected):
            my_te3_thread.wait()
        assert my_te3_thread.wait()

        my_te3_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            my_te3_thread.set()

        with pytest.raises(RemoteThreadNotAlive):
            my_te3_thread.wait(timeout=3)

        with pytest.raises(RemoteThreadNotAlive):
            my_te3_thread.wait_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            my_te3_thread.wait_until(WUCond.RemoteSet)

        assert my_te3_thread.alpha.thread is alpha_t
        assert my_te3_thread.beta.thread is my_te3_thread

        del my_te3_thread

        #######################################################################
        # mainline and ThreadApp - thread_app sets alpha and beta alternative
        #######################################################################
        class MyThreadEvent4(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, alpha=alpha_t, beta=self)
                with pytest.raises(WaitUntilTimeout):
                    self.wait_until(WUCond.ThreadsReady, timeout=0.001)
                self.alpha_t1 = alpha_t1

            def run(self):
                logger.debug('run started')
                self.wait_until(WUCond.ThreadsReady, timeout=0.001)
                assert self.alpha.thread is self.alpha_t1
                assert self.alpha.thread is alpha_t
                assert self.beta.thread is self
                my_run_thread = threading.current_thread()
                assert self.beta.thread is my_run_thread
                assert self.beta.thread is threading.current_thread()
                with pytest.raises(WaitDeadlockDetected):
                    self.wait()
                assert self.wait()
                self.set()
                logger.debug('run exiting')

        my_te4_thread = MyThreadEvent4(alpha_t)
        my_te4_thread.start()

        my_te4_thread.wait_until(WUCond.RemoteWaiting)
        with pytest.raises(WaitDeadlockDetected):
            my_te4_thread.wait()

        my_te4_thread.set()
        assert my_te4_thread.wait()

        my_te4_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            my_te4_thread.set()

        with pytest.raises(RemoteThreadNotAlive):
            my_te4_thread.wait()

        with pytest.raises(RemoteThreadNotAlive):
            my_te4_thread.wait_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            my_te4_thread.wait_until(WUCond.RemoteSet)

        assert my_te4_thread.alpha.thread is alpha_t
        assert my_te4_thread.beta.thread is my_te4_thread

    ###########################################################################
    # test_smart_event_set_threads_two_f_threads
    ###########################################################################
    def test_smart_event_set_threads_two_f_threads(self) -> None:
        """Test set_thread with thread_event_app."""

        #######################################################################
        # two threads - mainline sets alpha and beta
        #######################################################################
        def fa1(s_event):
            logger.debug('fa1 entered')
            my_fa_thread = threading.current_thread()
            assert s_event.alpha.thread is my_fa_thread
            s_event.wait_until(WUCond.ThreadsReady)
            logger.debug('fa1 about to wait')
            s_event.wait()
            logger.debug('fa1 back from wait')
            s_event.set()

        def fb1(s_event):
            logger.debug('fb1 entered')
            my_fb_thread = threading.current_thread()
            assert s_event.beta.thread is my_fb_thread

            logger.debug('fb1 about to set')
            s_event.set()
            s_event.wait()

            while True:
                try:
                    s_event.wait_until(WUCond.ThreadsReady, timeout=0.1)
                    time.sleep(0.1)
                except WaitUntilTimeout:
                    break


            with pytest.raises(RemoteThreadNotAlive):
                s_event.set()

            with pytest.raises(RemoteThreadNotAlive):
                s_event.wait()

            with pytest.raises(RemoteThreadNotAlive):
                s_event.wait_until(WUCond.RemoteWaiting)


        smart_event_ab1 = SmartEvent()
        fa1_thread = threading.Thread(target=fa1, args=(smart_event_ab1,))
        smart_event_ab1.set_thread(alpha=fa1_thread)

        fb1_thread = threading.Thread(target=fb1, args=(smart_event_ab1,))
        smart_event_ab1.set_thread(beta=fb1_thread)

        logger.debug('starting fa1_thread')
        fa1_thread.start()
        time.sleep(3)
        logger.debug('starting fb1_thread')
        fb1_thread.start()

        fa1_thread.join()
        fb1_thread.join()

        assert smart_event_ab1.alpha.thread is fa1_thread
        assert smart_event_ab1.beta.thread is fb1_thread

        del fa1_thread
        del fb1_thread
        del smart_event_ab1

        #######################################################################
        # two threads - fa2 and fb2 set their own threads
        #######################################################################
        def fa2(s_event):
            logger.debug('fa2 entered')
            my_fa_thread = threading.current_thread()
            s_event.set_thread(alpha=my_fa_thread)
            assert s_event.alpha.thread is my_fa_thread

            s_event.wait_until(WUCond.ThreadsReady)
            logger.debug('fa2 about to deadlock')
            with pytest.raises(WaitDeadlockDetected):
                logger.debug('fa2 about to wait')
                s_event.wait()
                logger.debug('fa2 back from wait')
            # try:
            #     logger.debug('fa2 about to wait')
            #     s_event.wait()
            #     logger.debug('fa2 back from wait')
            # except WaitDeadlockDetected:
            #     num_deadlocks[0] += 1

            logger.debug('fa2 about to wait_until')
            s_event.wait_until(WUCond.ThreadsReady, timeout=2)
            logger.debug('fa2 about to set')
            s_event.set()

            # logger.debug('fa2 about to wait')
            # s_event.wait()
            # logger.debug('fa2 back from wait')

            # logger.debug('fa2 about to wait 2')
            # s_event.wait()
            # logger.debug('fa2 back from wait 2')
            #
            # s_event.set()
            s_event.wait()
            logger.debug('fa2 exiting')

        def fb2(s_event):
            logger.debug('fb2 entered')
            my_fb_thread = threading.current_thread()
            s_event.set_thread(beta=threading.current_thread())
            assert s_event.beta.thread is my_fb_thread

            s_event.wait_until(WUCond.ThreadsReady)
            logger.debug('fb2 about to deadlock')
            with pytest.raises(WaitDeadlockDetected):
                logger.debug('fb2 about to wait')
                s_event.wait()
                logger.debug('fb2 back from wait')
            # try:
            #     logger.debug('fb2 about to wait')
            #     s_event.wait()
            #     logger.debug('fb2 back from wait')
            # except WaitDeadlockDetected:
            #     logger.debug('fb2 deadlock was detected')
            #     num_deadlocks[0] += 1
            logger.debug('fb2 about to wait_until')
            s_event.wait_until(WUCond.ThreadsReady, timeout=2)
            logger.debug('fb2 about to wait')
            s_event.wait()
            s_event.set()

            # logger.debug('fb2 about to set')
            # s_event.set()
            # logger.debug('fb2 about to wait 2')
            # s_event.wait()
            # logger.debug('fb2 back from wait 2')

            while True:
                try:
                    s_event.wait_until(WUCond.ThreadsReady, timeout=0.1)
                    time.sleep(0.1)
                except WaitUntilTimeout:
                    logger.debug('fb2 got the timeout')
                    break

            logger.debug('fb2 about to try set for RemoteThreadNotAlive')
            with pytest.raises(RemoteThreadNotAlive):
                s_event.set()

            logger.debug('fb2 about to try wait for RemoteThreadNotAlive')
            s_event.alpha.event.clear()  # undo the last set by fa1
            with pytest.raises(RemoteThreadNotAlive):
                s_event.wait()

            logger.debug('fb2 exiting')

        # num_deadlocks = [0]
        smart_event_ab2 = SmartEvent()
        fa2_thread = threading.Thread(target=fa2, args=(smart_event_ab2,))

        fb2_thread = threading.Thread(target=fb2, args=(smart_event_ab2,))

        fa2_thread.start()
        fb2_thread.start()

        fa2_thread.join()
        fb2_thread.join()

        assert smart_event_ab2.alpha.thread is fa2_thread
        assert smart_event_ab2.beta.thread is fb2_thread

###############################################################################
# TestSetExc Class
###############################################################################
class TestSetExc:
    ###########################################################################
    # test_smart_event_sync_f1
    ###########################################################################
    def test_smart_event_set_exc_f1(self) -> None:
        """Test set_thread with f1."""

        def f1(s_event):
            logger.debug('f1 beta entered')

            s_event.sync(log_msg='f1 beta sync point 1')

            while cmd[0] != Cmd.Exit:
                cmd2[0] = Cmd.Exit
                time.sleep(.2)

            s_event.sync(log_msg='f1 beta sync point 2')

            s_event.set(log_msg='f1 beta set 3')

            s_event.sync(log_msg='f1 beta sync point 4')

            logger.debug('f1 beta exiting 5')


        logger.debug('mainline entered')
        smart_event1 = SmartEvent(alpha=threading.current_thread())
        f1_thread = threading.Thread(target=f1, args=(smart_event1,))
        smart_event1.set_thread(beta=f1_thread)
        f1_thread.start()

        cmd = [0]
        cmd2 = [0]
        assert smart_event1.sync(log_msg='mainline sync point 1')

        while cmd2[0] != Cmd.Exit:
            time.sleep(.2)

        smart_event1.beta.sync_wait = True
        with pytest.raises(InconsistentFlagSettings):
            smart_event1.set(log_msg='alpha error set 1a')
        smart_event1.beta.sync_wait = False

        smart_event1.beta.deadlock = True
        with pytest.raises(InconsistentFlagSettings):
            smart_event1.set(log_msg='alpha error set 1b')
        smart_event1.beta.deadlock = False

        smart_event1.beta.conflict = True
        with pytest.raises(InconsistentFlagSettings):
            smart_event1.set(log_msg='alpha error set 1c')
        smart_event1.beta.conflict = False

        smart_event1.beta.waiting = True
        smart_event1.beta.conflict = True
        with pytest.raises(InconsistentFlagSettings):
            smart_event1.set(log_msg='alpha error set 1d')
        smart_event1.beta.waiting = False
        smart_event1.beta.conflict = False

        cmd[0] = Cmd.Exit

        smart_event1.sync(log_msg='mainline sync point 2')

        smart_event1.wait(log_msg='mainline wait 3')

        smart_event1.sync(log_msg='mainline sync point 4')

        f1_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.set(log_msg='mainline sync point 5')

        logger.debug('mainline exiting')

###############################################################################
# TestSync Class
###############################################################################
class TestSync:


    ###########################################################################
    # test_smart_event_sync_f1
    ###########################################################################
    def test_smart_event_sync_f1(self) -> None:
        """Test set_thread with f1."""

        def f1(s_event):
            logger.debug('f1 beta entered')

            # assert False

            s_event.sync(log_msg='f1 beta sync point 1')

            s_event.wait()

            s_event.sync(log_msg='f1 beta sync point 2')

            s_event.set()

            s_event.sync(log_msg='f1 beta sync point 3')

            s_event.sync(log_msg='f1 beta sync point 4')

            s_event.wait()

            logger.debug('f1 beta exiting')


        logger.debug('mainline entered')
        smart_event1 = SmartEvent(alpha=threading.current_thread())
        f1_thread = threading.Thread(target=f1, args=(smart_event1,))
        smart_event1.set_thread(beta=f1_thread)
        f1_thread.start()

        smart_event1.sync(log_msg='mainline sync point 1')

        smart_event1.set()

        smart_event1.sync(log_msg='mainline sync point 2')

        smart_event1.wait()

        smart_event1.sync(log_msg='mainline sync point 3')

        smart_event1.set()

        smart_event1.sync(log_msg='mainline sync point 4')

        f1_thread.join()

        # thread_exc.raise_exc()

        logger.debug('mainline exiting')

    ###########################################################################
    # test_smart_event_sync_exc
    ###########################################################################
    def test_smart_event_sync_exc(self,
                                 thread_exc: "ThreadExc") -> None:
        """Test set_thread with f1."""

        def f1(s_event):
            logger.debug('f1 beta entered')

            assert s_event.sync(log_msg='f1 beta sync point 1')

            with pytest.raises(ConflictDeadlockDetected):
                s_event.wait(log_msg='f1 beta wait 2')

            assert s_event.sync(log_msg='f1 beta sync point 3')

            s_event.set(log_msg='f1 beta set 4')

            assert s_event.sync(log_msg='f1 beta sync point 5')

            assert s_event.wait(log_msg='f1 beta wait 6')

            time.sleep(3)  # delay mainline sync 7 for timeout

            logger.debug('f1 beta exiting 8')


        logger.debug('mainline entered')
        smart_event1 = SmartEvent(alpha=threading.current_thread())
        f1_thread = threading.Thread(target=f1, args=(smart_event1,))
        smart_event1.set_thread(beta=f1_thread)
        f1_thread.start()

        assert smart_event1.sync(log_msg='mainline sync point 1')

        with pytest.raises(ConflictDeadlockDetected):
            smart_event1.sync(log_msg='mainline sync point 2')

        assert smart_event1.sync(log_msg='mainline sync point 3')

        assert smart_event1.wait(log_msg='mainline wait 4')

        assert smart_event1.sync(log_msg='mainline sync point 5')

        smart_event1.set(log_msg='mainline set 6')

        assert not smart_event1.sync(log_msg='mainline sync point 7',
                                     timeout=1)

        f1_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.sync(log_msg='mainline sync point 8')

        logger.debug('mainline exiting 9')

###############################################################################
# TestWaitClear Class
###############################################################################
class TestWaitClear:
    ###########################################################################
    # test_smart_event_f1_clear
    ###########################################################################
    def test_smart_event_f1_clear(self) -> None:
        """Test smart event timeout with f1 thread."""

        def f1(s_event):
            logger.debug('f1 entered')

            start_time = time.time()
            assert s_event.wait()
            duration = time.time() - start_time
            assert 3 <= duration <= 4
            assert not s_event.alpha.event.is_set()

            start_time = time.time()
            assert s_event.wait()
            duration = time.time() - start_time
            assert 3 <= duration <= 4
            assert not s_event.alpha.event.is_set()

            time.sleep(3)
            s_event.set()
            time.sleep(3)
            s_event.set()

        smart_event = SmartEvent(alpha=threading.current_thread())
        beta_thread = threading.Thread(target=f1, args=(smart_event,))
        smart_event.set_thread(beta=beta_thread)
        beta_thread.start()

        time.sleep(3)
        smart_event.set()
        time.sleep(3)
        smart_event.set()

        start_time = time.time()
        assert smart_event.wait()
        duration = time.time() - start_time
        assert 3 <= duration <= 4
        assert not smart_event.beta.event.is_set()

        start_time = time.time()
        assert smart_event.wait()
        duration = time.time() - start_time
        assert 3 <= duration <= 4
        assert not smart_event.beta.event.is_set()

        beta_thread.join()

    ###########################################################################
    # test_smart_event_thread_app_clear
    ###########################################################################
    def test_smart_event_thread_app_clear(self) -> None:
        """Test smart event timeout with thread_app thread."""

        class MyThread(threading.Thread):
            def __init__(self, s_event: SmartEvent):
                super().__init__()
                self.s_event = s_event
                self.s_event.set_thread(beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                assert not self.s_event.alpha.event.is_set()
                assert not self.s_event.beta.event.is_set()
                start_time = time.time()
                assert self.s_event.wait()
                duration = time.time() - start_time
                assert 3 <= duration <= 4
                assert not self.s_event.alpha.event.is_set()
                assert not self.s_event.beta.event.is_set()

                start_time = time.time()
                assert self.s_event.wait()
                duration = time.time() - start_time
                assert 3 <= duration <= 4
                assert not self.s_event.alpha.event.is_set()
                assert not self.s_event.beta.event.is_set()

                time.sleep(3)
                self.s_event.set()
                time.sleep(3)
                self.s_event.set()


        smart_event = SmartEvent(alpha=threading.current_thread())
        thread_app = MyThread(smart_event)
        thread_app.start()

        time.sleep(3)
        smart_event.set()
        time.sleep(3)
        smart_event.set()

        start_time = time.time()
        assert smart_event.wait()
        duration = time.time() - start_time
        assert 3 <= duration <= 4
        assert not smart_event.alpha.event.is_set()
        assert not smart_event.beta.event.is_set()

        start_time = time.time()
        assert smart_event.wait()
        duration = time.time() - start_time
        assert 3 <= duration <= 4
        assert not smart_event.alpha.event.is_set()
        assert not smart_event.beta.event.is_set()

        thread_app.join()

###############################################################################
# TestSmartEventTimeout Class
###############################################################################
class TestSmartEventTimeout:

    ###########################################################################
    # test_smart_event_f1_time_out
    ###########################################################################
    def test_smart_event_f1_time_out(self) -> None:
        """Test smart event timeout with f1 thread.

        Args:
            thread_exc: exception capture fixture

        Raises:
            Exception: any uncaptured exception from a thread

        """

        def f1(s_event):
            logger.debug('f1 entered')
            assert not s_event.wait(timeout=2)
            time.sleep(4)

        smart_event = SmartEvent(alpha=threading.current_thread())
        beta_thread = threading.Thread(target=f1, args=(smart_event,))
        smart_event.set_thread(beta=beta_thread)
        beta_thread.start()
        time.sleep(3)

        assert not smart_event.wait(timeout=2)

        beta_thread.join()

    ###########################################################################
    # test_smart_event_thread_app_time_out
    ###########################################################################
    def test_smart_event_thread_app_time_out(self) -> None:
        """Test smart event timeout with thread_app thread.

        Args:
            thread_exc: exception capture fixture

        Raises:
            Exception: any uncaptured exception from a thread

        """

        class MyThread(threading.Thread):
            def __init__(self, s_event: SmartEvent):
                super().__init__()
                self.s_event = s_event
                self.s_event.set_thread(beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')
                assert not self.s_event.wait(timeout=2)
                time.sleep(4)

        smart_event = SmartEvent(alpha=threading.current_thread())
        thread_app = MyThread(smart_event)
        thread_app.start()

        time.sleep(3)

        assert not smart_event.wait(timeout=2)

        thread_app.join()


###############################################################################
# TestSmartEventCode Class
###############################################################################
class TestSmartEventCode:

    ###########################################################################
    # test_smart_event_f1_event_code
    ###########################################################################
    def test_smart_event_f1_event_code(self) -> None:
        """Test smart event code with f1 thread."""
        def f1(s_event):
            logger.debug('f1 entered')
            assert not s_event.alpha.code
            assert not s_event.beta.code
            assert not s_event.get_code()

            s_event.sync(log_msg='beta sync point 1')

            assert s_event.wait(timeout=2)
            assert not s_event.alpha.code
            assert s_event.beta.code == 42
            assert 42 == s_event.get_code()

            s_event.sync(log_msg='beta sync point 2')

            s_event.set(code='forty-two')
            assert s_event.alpha.code == 'forty-two'
            assert s_event.beta.code == 42
            assert 42 == s_event.get_code()

            s_event.sync(log_msg='beta sync point 3')

            assert s_event.alpha.code == 'forty-two'
            assert s_event.beta.code == 42
            assert 42 == s_event.get_code()

            assert not s_event.wait(timeout=.5)

            assert s_event.alpha.code == 'forty-two'
            assert s_event.beta.code == 42
            assert 42 == s_event.get_code()

            s_event.sync(log_msg='beta sync point 4')
            s_event.sync(log_msg='beta sync point 5')

            assert s_event.alpha.code == 'forty-two'
            assert s_event.beta.code == 'twenty one'
            assert 'twenty one' == s_event.get_code()
            assert s_event.alpha.event.is_set()


        smart_event = SmartEvent(alpha=threading.current_thread())
        beta_thread = threading.Thread(target=f1, args=(smart_event,))
        smart_event.set_thread(beta=beta_thread)
        beta_thread.start()
        smart_event.wait_until(WUCond.ThreadsReady)

        smart_event.sync(log_msg='mainline sync point 1')

        assert not smart_event.get_code()
        assert not smart_event.alpha.code
        assert not smart_event.beta.code

        smart_event.set(code=42)

        assert not smart_event.get_code()
        assert not smart_event.alpha.code
        assert smart_event.beta.code == 42

        smart_event.sync(log_msg='mainline sync point 2')

        assert smart_event.wait()

        assert smart_event.get_code() == 'forty-two'
        assert smart_event.alpha.code == 'forty-two'
        assert smart_event.beta.code == 42

        smart_event.sync(log_msg='mainline sync point 3')
        smart_event.sync(log_msg='mainline sync point 4')

        smart_event.set(code='twenty one')

        smart_event.sync(log_msg='mainline sync point 5')

        beta_thread.join()

    ###########################################################################
    # test_smart_event_thread_app_event_code
    ###########################################################################
    def test_smart_event_thread_app_event_code(self) -> None:
        """Test smart event code with thread_app thread."""

        class MyThread(threading.Thread):
            def __init__(self, s_event: SmartEvent):
                super().__init__()
                self.s_event = s_event
                self.s_event.set_thread(beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')
                assert self.s_event.get_code() is None
                assert not self.s_event.wait(timeout=2, log_msg='beta wait 1')

                self.s_event.sync(log_msg='beta sync point 2')
                self.s_event.sync(log_msg='beta sync point 3')

                assert self.s_event.alpha.event.is_set()
                assert self.s_event.beta.code == 42
                assert self.s_event.get_code() == 42

                self.s_event.set(log_msg='beta set 4',
                                 code='forty-two')

        smart_event = SmartEvent(alpha=threading.current_thread())
        thread_app = MyThread(smart_event)
        thread_app.start()
        smart_event.wait_until(WUCond.ThreadsReady)

        smart_event.sync(log_msg='mainline sync point 2')
        smart_event.set(code=42)
        smart_event.sync(log_msg='mainline sync point 3')

        assert smart_event.wait(log_msg='mainline wait 4')
        assert smart_event.get_code() == 'forty-two'

        thread_app.join()

    ###########################################################################
    # test_smart_event_thread_event_app_event_code
    ###########################################################################
    def test_smart_event_thread_event_app_event_code(self) -> None:
        """Test smart event code with thread_event_app thread."""

        class MyThread(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha: threading.Thread) -> None:
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, alpha=alpha, beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                assert not self.alpha.code
                assert not self.beta.code
                assert not self.get_code()

                self.sync(log_msg='beta sync point 1')

                assert not self.wait(timeout=0.5)

                assert not self.alpha.code
                assert not self.beta.code
                assert not self.get_code()

                self.sync(log_msg='beta sync point 2')
                self.sync(log_msg='beta sync point 3')

                assert not self.alpha.code
                assert self.beta.code == 42
                assert self.get_code() == 42

                self.set(code='forty-two')

                assert self.alpha.code == 'forty-two'
                assert self.beta.code == 42
                assert self.get_code() == 42

                self.sync(log_msg='beta sync point 4')
                self.sync(log_msg='beta sync point 5')

                assert self.alpha.code == 'forty-two'
                assert self.beta.code == 42
                assert self.get_code() == 42

                assert self.wait(timeout=0.5, log_msg='beta wait 56')

                assert self.alpha.code == 'forty-two'
                assert self.beta.code == 42
                assert self.get_code() == 42

                self.sync(log_msg='beta sync point 6')

        thread_event_app = MyThread(alpha=threading.current_thread())
        thread_event_app.start()
        thread_event_app.wait_until(WUCond.ThreadsReady)

        assert not thread_event_app.alpha.code
        assert not thread_event_app.beta.code
        assert not thread_event_app.get_code()

        thread_event_app.sync(log_msg='mainline sync point 1')
        thread_event_app.sync(log_msg='mainline sync point 2')

        assert not thread_event_app.alpha.code
        assert not thread_event_app.beta.code
        assert not thread_event_app.get_code()

        thread_event_app.set(code=42, log_msg='mainline set for beta 56')

        assert not thread_event_app.alpha.code
        assert thread_event_app.beta.code == 42
        assert not thread_event_app.get_code()

        thread_event_app.sync(log_msg='mainline sync point 3')
        thread_event_app.sync(log_msg='mainline sync point 4')

        assert thread_event_app.alpha.code == 'forty-two'
        assert thread_event_app.beta.code == 42
        assert thread_event_app.get_code() == 'forty-two'

        assert thread_event_app.wait()

        assert thread_event_app.alpha.code == 'forty-two'
        assert thread_event_app.beta.code == 42
        assert thread_event_app.get_code() == 'forty-two'

        thread_event_app.sync(log_msg='mainline sync point 5')

        assert thread_event_app.alpha.code == 'forty-two'
        assert thread_event_app.beta.code == 42
        assert thread_event_app.get_code() == 'forty-two'

        thread_event_app.sync(log_msg='mainline sync point 6')

        thread_event_app.join()

###############################################################################
# TestSmartEventLogger Class
###############################################################################
class TestSmartEventLogger:

    ###########################################################################
    # test_smart_event_f1_event_logger
    ###########################################################################
    def test_smart_event_f1_event_logger(self,
                                         caplog) -> None:
        """Test smart event logger with f1 thread.

        Args:
            caplog: fixture to capture log messages

        """

        def f1(s_event):
            logger.debug('f1 entered')

            s_event.sync(log_msg='beta sync point 1')

            assert s_event.wait(log_msg='wait for mainline to post 12')

            s_event.sync(log_msg='beta sync point 2')

            s_event.set(log_msg='post mainline 23')

            s_event.sync(log_msg='beta sync point 3')
            s_event.sync(log_msg='beta sync point 4')

        logger.debug('mainline started')
        smart_event = SmartEvent(alpha=threading.current_thread())
        beta_thread = threading.Thread(target=f1, args=(smart_event,))
        smart_event.set_thread(beta=beta_thread)
        beta_thread.start()
        smart_event.wait_until(WUCond.ThreadsReady)

        smart_event.sync(log_msg='mainline sync point 1')
        smart_event.wait_until(WUCond.RemoteWaiting)

        smart_event.set(log_msg=f'post beta 12')

        smart_event.sync(log_msg='mainline sync point 2')
        smart_event.sync(log_msg='mainline sync point 3')

        assert smart_event.wait(log_msg='wait for pre-post 23')

        smart_event.sync(log_msg='mainline sync point 4')

        beta_thread.join()

        logger.debug('mainline all tests complete')

        #######################################################################
        # verify log messages
        #######################################################################
        ml_log_seq = ('test_smart_event.py::TestSmartEventLogger.'
                      'test_smart_event_f1_event_logger:[0-9]* ')

        beta_log_seq = ('test_smart_event.py::f1:[0-9]* ')

        ml_sync_enter_log_prefix = ('sync entered ' + ml_log_seq)

        ml_sync_exit_log_prefix = ('sync exiting ' + ml_log_seq)

        ml_wait_enter_log_prefix = ('wait entered ' + ml_log_seq)

        ml_wait_exit_log_prefix = ('wait exiting ' + ml_log_seq)

        ml_set_enter_log_prefix = ('set entered ' + ml_log_seq)

        ml_set_exit_log_prefix = ('set exiting ' + ml_log_seq)

        beta_sync_enter_log_prefix = ('sync entered ' + beta_log_seq)

        beta_sync_exit_log_prefix = ('sync exiting ' + beta_log_seq)

        beta_wait_enter_log_prefix = ('wait entered ' + beta_log_seq)

        beta_wait_exit_log_prefix = ('wait exiting ' + beta_log_seq)

        beta_set_enter_log_prefix = ('set entered ' + beta_log_seq)

        beta_set_exit_log_prefix = ('set exiting ' + beta_log_seq)


        exp_log_msgs = [
            re.compile('mainline started'),
            re.compile('mainline all tests complete'),

            re.compile(ml_sync_enter_log_prefix + 'mainline sync point 1'),
            re.compile(ml_sync_exit_log_prefix + 'mainline sync point 1'),
            re.compile(ml_sync_enter_log_prefix + 'mainline sync point 2'),
            re.compile(ml_sync_exit_log_prefix + 'mainline sync point 2'),
            re.compile(ml_sync_enter_log_prefix + 'mainline sync point 3'),
            re.compile(ml_sync_exit_log_prefix + 'mainline sync point 3'),
            re.compile(ml_sync_enter_log_prefix + 'mainline sync point 4'),
            re.compile(ml_sync_exit_log_prefix + 'mainline sync point 4'),

            re.compile(ml_wait_enter_log_prefix + 'wait for pre-post 23'),
            re.compile(ml_wait_exit_log_prefix + 'wait for pre-post 23'),

            re.compile(ml_set_enter_log_prefix + 'post beta 12'),
            re.compile(ml_set_exit_log_prefix + 'post beta 12'),

            re.compile('f1 entered'),
            re.compile(beta_sync_enter_log_prefix + 'beta sync point 1'),
            re.compile(beta_sync_exit_log_prefix + 'beta sync point 1'),
            re.compile(beta_sync_enter_log_prefix + 'beta sync point 2'),
            re.compile(beta_sync_exit_log_prefix + 'beta sync point 2'),
            re.compile(beta_sync_enter_log_prefix + 'beta sync point 3'),
            re.compile(beta_sync_exit_log_prefix + 'beta sync point 3'),
            re.compile(beta_sync_enter_log_prefix + 'beta sync point 4'),
            re.compile(beta_sync_exit_log_prefix + 'beta sync point 4'),

            re.compile(beta_wait_enter_log_prefix
                       + 'wait for mainline to post 12'),
            re.compile(beta_wait_exit_log_prefix
                       + 'wait for mainline to post 12'),

            re.compile(beta_set_enter_log_prefix + 'post mainline 23'),
            re.compile(beta_set_exit_log_prefix + 'post mainline 23'),
                        ]

        log_records_found = 0
        # caplog_recs = []
        # for record in caplog.records:
        #     caplog_recs.append(record.msg)

        for idx, record in enumerate(caplog.records):
            # print(record.msg)
            # print(exp_log_msgs)
            for idx2, l_msg in enumerate(exp_log_msgs):
                if l_msg.match(record.msg):
                    # print(l_msg.match(record.msg))
                    exp_log_msgs.pop(idx2)
                    # caplog_recs.remove(record.msg)
                    log_records_found += 1
                    break

        # print(f'\nlog_records_found: {log_records_found} of {len(caplog.records)}')
        #
        # print('*' * 20)
        # for log_msg in caplog_recs:
        #     print(log_msg)
        #
        # print('*' * 20)
        # for exp_lm in exp_log_msgs:
        #     print(exp_lm)

        assert not exp_log_msgs
        assert log_records_found == len(caplog.records)

    ###########################################################################
    # test_smart_event_thread_app_event_logger
    ###########################################################################
    def test_smart_event_thread_app_event_logger(self,
                                                 caplog) -> None:
        """Test smart event logger with thread_app thread.

        Args:
            caplog: fixture to capture log messages

        """

        class MyThread(threading.Thread):
            def __init__(self, s_event: SmartEvent):
                super().__init__()
                self.s_event = s_event
                self.s_event.set_thread(beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')
                self.s_event.sync(log_msg='beta sync point 1')

                assert self.s_event.wait(log_msg='wait 12')

                self.s_event.sync(log_msg='beta sync point 2')

                self.s_event.wait_until(WUCond.RemoteWaiting)

                self.s_event.set(code='forty-two', log_msg='post mainline 34')

                self.s_event.sync(log_msg='beta sync point 3')
                self.s_event.sync(log_msg='beta sync point 4')

        logger.debug('mainline starting')
        smart_event = SmartEvent(alpha=threading.current_thread())
        thread_app = MyThread(smart_event)
        thread_app.start()
        smart_event.wait_until(WUCond.ThreadsReady)

        smart_event.sync(log_msg='mainline sync point 1')

        smart_event.wait_until(WUCond.RemoteWaiting)

        smart_event.set(log_msg=f'post thread {smart_event.beta.name} 23',
                        code=42)

        smart_event.sync(log_msg='mainline sync point 2')

        assert smart_event.wait(log_msg='wait for post from thread 34')

        smart_event.sync(log_msg='mainline sync point 3')
        smart_event.sync(log_msg='mainline sync point 4')

        thread_app.join()

        logger.debug('mainline all tests complete')

        #######################################################################
        # verify log messages
        #######################################################################
        ml_log_seq = ('test_smart_event.py::TestSmartEventLogger.'
                      'test_smart_event_thread_app_event_logger:[0-9]* ')

        beta_log_seq = ('test_smart_event.py::MyThread.run:[0-9]* ')

        ml_sync_enter_log_prefix = ('sync entered ' + ml_log_seq)

        ml_sync_exit_log_prefix = ('sync exiting ' + ml_log_seq)

        ml_wait_enter_log_prefix = ('wait entered ' + ml_log_seq)

        ml_wait_exit_log_prefix = ('wait exiting ' + ml_log_seq)

        ml_set_enter_log_prefix = ('set entered with code: 42 ' + ml_log_seq)

        ml_set_exit_log_prefix = ('set exiting ' + ml_log_seq)

        beta_sync_enter_log_prefix = ('sync entered ' + beta_log_seq)

        beta_sync_exit_log_prefix = ('sync exiting ' + beta_log_seq)

        beta_wait_enter_log_prefix = ('wait entered ' + beta_log_seq)

        beta_wait_exit_log_prefix = ('wait exiting ' + beta_log_seq)

        beta_set_enter_log_prefix = ('set entered with code: forty-two '
                                     + beta_log_seq)

        beta_set_exit_log_prefix = ('set exiting ' + beta_log_seq)


        exp_log_msgs = [
            re.compile('mainline starting'),
            re.compile('mainline all tests complete'),

            re.compile(ml_sync_enter_log_prefix + 'mainline sync point 1'),
            re.compile(ml_sync_exit_log_prefix + 'mainline sync point 1'),
            re.compile(ml_sync_enter_log_prefix + 'mainline sync point 2'),
            re.compile(ml_sync_exit_log_prefix + 'mainline sync point 2'),
            re.compile(ml_sync_enter_log_prefix + 'mainline sync point 3'),
            re.compile(ml_sync_exit_log_prefix + 'mainline sync point 3'),
            re.compile(ml_sync_enter_log_prefix + 'mainline sync point 4'),
            re.compile(ml_sync_exit_log_prefix + 'mainline sync point 4'),

            re.compile(ml_wait_enter_log_prefix
                       + 'wait for post from thread 34'),
            re.compile(ml_wait_exit_log_prefix
                       + 'wait for post from thread 34'),

            re.compile(ml_set_enter_log_prefix + 'post thread beta 23'),
            re.compile(ml_set_exit_log_prefix + 'post thread beta 23'),

            re.compile('ThreadApp run entered'),
            re.compile(beta_sync_enter_log_prefix + 'beta sync point 1'),
            re.compile(beta_sync_exit_log_prefix + 'beta sync point 1'),
            re.compile(beta_sync_enter_log_prefix + 'beta sync point 2'),
            re.compile(beta_sync_exit_log_prefix + 'beta sync point 2'),
            re.compile(beta_sync_enter_log_prefix + 'beta sync point 3'),
            re.compile(beta_sync_exit_log_prefix + 'beta sync point 3'),
            re.compile(beta_sync_enter_log_prefix + 'beta sync point 4'),
            re.compile(beta_sync_exit_log_prefix + 'beta sync point 4'),

            re.compile(beta_wait_enter_log_prefix + 'wait 12'),
            re.compile(beta_wait_exit_log_prefix + 'wait 12'),

            re.compile(beta_set_enter_log_prefix + 'post mainline 34'),
            re.compile(beta_set_exit_log_prefix + 'post mainline 34'),
                        ]

        log_records_found = 0
        caplog_recs = []
        for record in caplog.records:
            caplog_recs.append(record.msg)

        for idx, record in enumerate(caplog.records):
            # print(record.msg)
            # print(exp_log_msgs)
            for idx2, l_msg in enumerate(exp_log_msgs):
                if l_msg.match(record.msg):
                    # print(l_msg.match(record.msg))
                    exp_log_msgs.pop(idx2)
                    caplog_recs.remove(record.msg)
                    log_records_found += 1
                    break

        print(f'\nlog_records_found: {log_records_found} of {len(caplog.records)}')

        print('*' * 20)
        for log_msg in caplog_recs:
            print(log_msg)

        print('*' * 20)
        for exp_lm in exp_log_msgs:
            print(exp_lm)

        assert not exp_log_msgs
        assert log_records_found == len(caplog.records)

    ###########################################################################
    # test_smart_event_thread_event_app_event_logger
    ###########################################################################
    def test_smart_event_thread_event_app_event_logger(self, caplog) -> None:
        """Test smart event logger with thread_event_app thread.

        Args:
            caplog: fixture to capture log messages

        """

        class MyThread(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, alpha=alpha, beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')
                self.sync(log_msg='beta sync point 1')

                assert self.wait(log_msg='wait for mainline to post 12')

                self.sync(log_msg='beta sync point 2')

                self.wait_until(WUCond.RemoteWaiting)

                self.set(log_msg='post mainline 23')

                self.sync(log_msg='beta sync point 3')

        logger.debug('mainline starting')
        thread_event_app = MyThread(alpha=threading.current_thread())
        thread_event_app.start()

        thread_event_app.wait_until(WUCond.ThreadsReady)

        thread_event_app.sync(log_msg='mainline sync point 1')

        thread_event_app.wait_until(WUCond.RemoteWaiting)

        thread_event_app.set(log_msg=f'post thread '
                                     f'{thread_event_app.beta.name} 12')

        thread_event_app.sync(log_msg='mainline sync point 2')

        assert thread_event_app.wait(log_msg='wait for post from thread 23')

        thread_event_app.sync(log_msg='mainline sync point 3')

        thread_event_app.join()

        logger.debug('mainline all tests complete')

        #######################################################################
        # verify log messages
        #######################################################################
        ml_log_seq = ('test_smart_event.py::TestSmartEventLogger.'
                      'test_smart_event_thread_event_app_event_logger:[0-9]* ')

        beta_log_seq = ('test_smart_event.py::MyThread.run:[0-9]* ')

        ml_sync_enter_log_prefix = ('sync entered ' + ml_log_seq)

        ml_sync_exit_log_prefix = ('sync exiting ' + ml_log_seq)

        ml_wait_enter_log_prefix = ('wait entered ' + ml_log_seq)

        ml_wait_exit_log_prefix = ('wait exiting ' + ml_log_seq)

        ml_set_enter_log_prefix = ('set entered ' + ml_log_seq)

        ml_set_exit_log_prefix = ('set exiting ' + ml_log_seq)

        beta_sync_enter_log_prefix = ('sync entered ' + beta_log_seq)

        beta_sync_exit_log_prefix = ('sync exiting ' + beta_log_seq)

        beta_wait_enter_log_prefix = ('wait entered ' + beta_log_seq)

        beta_wait_exit_log_prefix = ('wait exiting ' + beta_log_seq)

        beta_set_enter_log_prefix = ('set entered ' + beta_log_seq)

        beta_set_exit_log_prefix = ('set exiting ' + beta_log_seq)


        exp_log_msgs = [
            re.compile('mainline starting'),
            re.compile('mainline all tests complete'),

            re.compile(ml_sync_enter_log_prefix + 'mainline sync point 1'),
            re.compile(ml_sync_exit_log_prefix + 'mainline sync point 1'),
            re.compile(ml_sync_enter_log_prefix + 'mainline sync point 2'),
            re.compile(ml_sync_exit_log_prefix + 'mainline sync point 2'),
            re.compile(ml_sync_enter_log_prefix + 'mainline sync point 3'),
            re.compile(ml_sync_exit_log_prefix + 'mainline sync point 3'),

            re.compile(ml_wait_enter_log_prefix
                       + 'wait for post from thread 23'),
            re.compile(ml_wait_exit_log_prefix
                       + 'wait for post from thread 23'),

            re.compile(ml_set_enter_log_prefix + 'post thread beta 12'),
            re.compile(ml_set_exit_log_prefix + 'post thread beta 12'),

            re.compile('ThreadApp run entered'),
            re.compile(beta_sync_enter_log_prefix + 'beta sync point 1'),
            re.compile(beta_sync_exit_log_prefix + 'beta sync point 1'),
            re.compile(beta_sync_enter_log_prefix + 'beta sync point 2'),
            re.compile(beta_sync_exit_log_prefix + 'beta sync point 2'),
            re.compile(beta_sync_enter_log_prefix + 'beta sync point 3'),
            re.compile(beta_sync_exit_log_prefix + 'beta sync point 3'),

            re.compile(beta_wait_enter_log_prefix
                       + 'wait for mainline to post 12'),
            re.compile(beta_wait_exit_log_prefix
                       + 'wait for mainline to post 12'),

            re.compile(beta_set_enter_log_prefix + 'post mainline 23'),
            re.compile(beta_set_exit_log_prefix + 'post mainline 23'),
                        ]

        log_records_found = 0
        caplog_recs = []
        for record in caplog.records:
            caplog_recs.append(record.msg)

        for idx, record in enumerate(caplog.records):
            # print(record.msg)
            # print(exp_log_msgs)
            for idx2, l_msg in enumerate(exp_log_msgs):
                if l_msg.match(record.msg):
                    # print(l_msg.match(record.msg))
                    exp_log_msgs.pop(idx2)
                    caplog_recs.remove(record.msg)
                    log_records_found += 1
                    break

        print(f'\nlog_records_found: {log_records_found} of {len(caplog.records)}')

        print('*' * 20)
        for log_msg in caplog_recs:
            print(log_msg)

        print('*' * 20)
        for exp_lm in exp_log_msgs:
            print(exp_lm)

        assert not exp_log_msgs
        assert log_records_found == len(caplog.records)

###############################################################################
# TestCombos Class
###############################################################################
class TestCombos:
    ###########################################################################
    # test_smart_event_thread_app_combos
    ###########################################################################
    def test_smart_event_thread_app_combos(self,
                                           action_arg1: Any,
                                           timeout_arg1: Any,
                                           code_arg1: Any,
                                           log_msg_arg1: Any,
                                           action_arg2: Any,
                                           timeout_arg2: Any,
                                           # code_arg2: Any,
                                           # log_msg_arg2: Any,
                                           thread_exc: "ExcHook" ) -> None:
        """Test the SmartEvent with ThreadApp combos.

        Args:
            action_arg1: first action
            timeout_arg1: whether to specify timeout
            code_arg1: whether to set and recv a code
            log_msg_arg1: whether to specify a log message
            action_arg2: second action
            timeout_arg2: whether to specify timeout
            code_arg2: whether to set and recv a code
            log_msg_arg2: whether to specify a log message

        Raises:
            IncorrectActionSpecified: The Action is not recognized

        """
        # class SmartEventApp(threading.Thread):
        #     def __init__(self,
        #                  smart_event: SmartEvent) -> None:
        #         super().__init__()
        #         self.smart_event = smart_event
        #
        #     def run(self):
        #         """Thread to send and receive messages.
        #
        #         Raises:
        #             UnrecognizedCmd: SmartEventApp received an
        #                                       unrecognized action
        #         """
        #         logger.debug('SmartEventApp run started')



        smart_event = SmartEvent()
        cmd_to_thread = [0]
        cmd_to_mainline = [0]
        cmd_log = [0]
        cmd_timeout = [0]
        cmd_timeout_result = [False]

        f1_thread = threading.Thread(target=self.thread_func1,
                                     args=(smart_event,
                                           cmd_to_thread,
                                           cmd_to_mainline,
                                           cmd_log,
                                           cmd_timeout,
                                           cmd_timeout_result))

        logger.debug('mainline about to start thread_func1')
        f1_thread.start()

        #######################################################################
        # action loop
        #######################################################################
        actions = []
        actions.append(action_arg1)
        actions.append(action_arg2)
        for action in actions:
            if action == Action.MainWait:
                logger.debug('main starting Action.MainWait')

            elif action == Action.MainSet:
                logger.debug('main starting Action.MainSet')
                smart_event.set()
                cmd_to_thread[0] = Cmd.Wait

            elif action == Action.ThreadWait:
                logger.debug('main starting Action.ThreadWait')

            elif action == Action.ThreadSet:
                logger.debug('main starting Action.ThreadSet')

            else:
                raise IncorrectActionSpecified('The Action is not recognized')

            while True:
                if cmd_to_mainline[0] == Cmd.Exit:
                    break
                thread_exc.raise_exc_if_one()  # detect thread error
                time.sleep(0.2)

        logger.debug('main completed all actions')
        cmd_to_thread[0] = Cmd.Exit

        f1_thread.join()

###############################################################################
# thread_func1
###############################################################################
    def thread_func1(self,
                     s_event: SmartEvent,
                     cmd_to_thread: List[Any],
                     cmd_to_mainline: List[Any],
                     cmd_log: List[Any],
                     cmd_timeout: List[Any],
                     cmd_timeout_result: List[Any]
                     ) -> None:

        """Thread to test SmartEvent scenarios.

        Args:
            s_event: instance of SmartEvent
            cmd_to_thread: command from mainline to this thread to perform
            cmd_to_mainline: command from this thread to mainline to perform
            cmd_log: specifies whether to issue a log_msg
            cmd_timeout: specifies whether to issue a timeout
            cmd_timeout_result: specifies whether a timeout times out

        Raises:
            UnrecognizedCmd: Thread received an unrecognized command

        """
        logger.debug('thread_func1 beta started')
        while True:
            if cmd_to_thread[0] == Cmd.Wait:
                cmd_to_thread[0] = 0
                logger.debug('thread_func1 doing wait')
                if not cmd_log[0] and not cmd_timeout[0]:
                    s_event.wait()
                elif not cmd_log[0] and cmd_timeout[0]:
                    if cmd_timeout_result[0]:
                        assert s_event.wait(timeout=cmd_timeout[0])
                    else:
                        start_time = time.time()
                        assert not s_event.wait(timeout=cmd_timeout[0])
                        assert (cmd_timeout[0]
                                    < (time.time() - start_time)
                                    < (cmd_timeout[0] + .5))

                elif cmd_log[0] and not cmd_timeout[0]:
                    assert s_event.wait(log_msg=cmd_log[0])

                elif cmd_log[0] and cmd_timeout[0]:
                    if cmd_timeout_result[0]:
                        assert s_event.wait(log_msg=cmd_log[0],
                                            timeout=cmd_timeout[0])
                    else:
                        start_time = time.time()
                        assert not s_event.wait(timeout=cmd_timeout[0],
                                                log_msg=cmd_log[0])
                        assert (cmd_timeout[0]
                                < (time.time() - start_time)
                                < (cmd_timeout[0] + .5))

                cmd_to_mainline[0] = Cmd.Exit

            elif cmd_to_thread[0] == Cmd.Exit:
                logger.debug('thread_func1 beta exiting')
                break

            # elif cmd_to_thread[0] == 0:
            #     time.sleep(0.2)

            else:
                raise UnrecognizedCmd('Thread received an unrecognized cmd')

            time.sleep(0.2)
