"""test_smart_event.py module."""

from enum import Enum
import time
import math
import pytest
from typing import Any, cast, List, Optional
from sys import _getframe
import threading
# from scottbrian_utils.diag_msg import diag_msg
from scottbrian_utils.smart_event import (SmartEvent,
                                          IncorrectThreadSpecified,
                                          ThreadAlreadySet,
                                          DuplicateThreadSpecified,
                                          TargetThreadNotAlive,
                                          IncorrectChildThreadSpecified,
                                          WaitAttemptedBeforeThreadsSet,
                                          SetAttemptedBeforeThreadsSet)

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


class UnrecognizedActionToDo(ErrorTstSmartEvent):
    """UnrecognizedActionToDo exception class."""
    pass


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
def action1_arg(request: Any) -> Any:
    """Using different reply messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


@pytest.fixture(params=action_arg_list)  # type: ignore
def action2_arg(request: Any) -> Any:
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
code_arg_list = [None, 42, 'forty-two']


@pytest.fixture(params=code_arg_list)  # type: ignore
def code1_arg(request: Any) -> Any:
    """Using different codes.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=code_arg_list)  # type: ignore
def code2_arg(request: Any) -> Any:
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
log_msg_arg_list = [None, 'log msg1', 'log msg2']


@pytest.fixture(params=log_msg_arg_list)  # type: ignore
def log_msg1_arg(request: Any) -> Any:
    """Using different log messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=log_msg_arg_list)  # type: ignore
def log_msg2_arg(request: Any) -> Any:
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
    def test_smart_event_repr(self) -> None:
        """test event with code repr."""
        smart_event = SmartEvent()

        expected_repr_str = 'SmartEvent()'

        assert repr(smart_event) == expected_repr_str

    ###########################################################################
    # test_smart_event_set_thread_alpha_first
    ###########################################################################
    def test_smart_event_set_thread_alpha_first(self) -> None:
        """Test set_thread alpha first."""

        def my_excepthook(exc_type, exc_value, exc_traceback, thread):
            print(f'in excepthook with args {exc_type}, {exc_value}, '
                  f'{exc_traceback}, {thread}')
            raise Exception(f'{exc_type}, {exc_value}, {exc_traceback}, '
                            f'{thread}')

        threading.excepthook = my_excepthook

        alpha_t = threading.current_thread()
        beta_t = threading.Thread()
        smart_event = SmartEvent()

        assert smart_event.alpha_thread is None
        assert smart_event.beta_thread is None

        # try wait and set without threads set
        with pytest.raises(WaitAttemptedBeforeThreadsSet):
            smart_event.wait()

        with pytest.raises(SetAttemptedBeforeThreadsSet):
            smart_event.set()

        with pytest.raises(IncorrectThreadSpecified):
            smart_event.set_thread(alpha=3)
            
        with pytest.raises(IncorrectThreadSpecified):
            smart_event.set_thread(beta=3)

        assert smart_event.alpha_thread is None
        assert smart_event.beta_thread is None

        # set alpha
        smart_event.set_thread(alpha=alpha_t)
        assert smart_event.alpha_thread is alpha_t
        assert smart_event.beta_thread is None

        # not OK to set alpha once set, even with same thread
        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(alpha=beta_t)
        assert smart_event.alpha_thread is alpha_t
        assert smart_event.beta_thread is None

        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(alpha=alpha_t)
        assert smart_event.alpha_thread is alpha_t
        assert smart_event.beta_thread is None

        # not OK to set beta to same thread as alpha
        with pytest.raises(DuplicateThreadSpecified):
            smart_event.set_thread(beta=alpha_t)
        assert smart_event.alpha_thread is alpha_t
        assert smart_event.beta_thread is None

        smart_event.set_thread(beta=beta_t)

        assert smart_event.alpha_thread is alpha_t
        assert smart_event.beta_thread is beta_t

        # not OK to set same beta thread
        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(beta=beta_t)

        assert smart_event.alpha_thread is alpha_t
        assert smart_event.beta_thread is beta_t

        # not OK to set different beta thread
        beta2 = threading.Thread()
        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(beta=beta2)

        assert smart_event.alpha_thread is alpha_t
        assert smart_event.beta_thread is beta_t

    ###########################################################################
    # test_smart_event_set_thread_beta_first
    ###########################################################################
    def test_smart_event_set_thread_beta_first(self) -> None:
        """Test set_thread beta first."""

        def my_excepthook(exc_type, exc_value, exc_traceback, thread):
            print(f'in excepthook with args {exc_type}, {exc_value}, '
                  f'{exc_traceback}, {thread}')
            raise Exception(f'{exc_type}, {exc_value}, {exc_traceback}, '
                            f'{thread}')

        threading.excepthook = my_excepthook

        alpha_t = threading.current_thread()
        beta_t = threading.Thread()
        smart_event = SmartEvent()

        assert smart_event.alpha_thread is None
        assert smart_event.beta_thread is None

        with pytest.raises(IncorrectThreadSpecified):
            smart_event.set_thread(alpha=3)

        with pytest.raises(IncorrectThreadSpecified):
            smart_event.set_thread(beta=3)

        assert smart_event.alpha_thread is None
        assert smart_event.beta_thread is None

        # set beta
        smart_event.set_thread(beta=beta_t)
        assert smart_event.alpha_thread is None
        assert smart_event.beta_thread is beta_t

        # not OK to set beta once set, even with same thread
        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(beta=alpha_t)
        assert smart_event.alpha_thread is None
        assert smart_event.beta_thread is beta_t

        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(beta=beta_t)
        assert smart_event.alpha_thread is None
        assert smart_event.beta_thread is beta_t

        # not OK to set alpha to same thread as beta
        with pytest.raises(DuplicateThreadSpecified):
            smart_event.set_thread(alpha=beta_t)
        assert smart_event.alpha_thread is None
        assert smart_event.beta_thread is beta_t

        smart_event.set_thread(alpha=alpha_t)

        assert smart_event.alpha_thread is alpha_t
        assert smart_event.beta_thread is beta_t

        # not OK to set same alpha thread
        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(alpha=alpha_t)

        assert smart_event.alpha_thread is alpha_t
        assert smart_event.beta_thread is beta_t

        # not OK to set different alpha thread
        alpha2 = threading.Thread()
        with pytest.raises(ThreadAlreadySet):
            smart_event.set_thread(alpha=alpha2)

        assert smart_event.alpha_thread is alpha_t
        assert smart_event.beta_thread is beta_t

    ###########################################################################
    # test_smart_event_set_threads_instantiate
    ###########################################################################
    def test_smart_event_set_threads_instantiate(self) -> None:
        """Test set_thread during instantiation."""

        def my_excepthook(exc_type, exc_value, exc_traceback, thread):
            print(f'in excepthook with args {exc_type}, {exc_value}, '
                  f'{exc_traceback}, {thread}')
            raise Exception(f'{exc_type}, {exc_value}, {exc_traceback}, '
                            f'{thread}')

        threading.excepthook = my_excepthook

        alpha_t = threading.current_thread()
        beta_t = threading.Thread()

        smart_e1 = SmartEvent(alpha=alpha_t, beta=beta_t)
        assert smart_e1.alpha_thread is alpha_t
        assert smart_e1.beta_thread is beta_t

        smart_e2 = SmartEvent(alpha=alpha_t)
        assert smart_e2.alpha_thread is alpha_t
        assert smart_e2.beta_thread is None

        smart_e3 = SmartEvent(beta=beta_t)
        assert smart_e3.alpha_thread is None
        assert smart_e3.beta_thread is beta_t

        # not OK to set alpha with bad value
        with pytest.raises(IncorrectThreadSpecified):
            smart_e4 = SmartThread(alpha=42)

        # not OK to set beta with bad value
        with pytest.raises(IncorrectThreadSpecified):
            smart_e5 = SmartThread(beta=17)

        # not OK to set alpha and beta both to same thread
        with pytest.raises(DuplicateThreadSpecified):
            smart_e6 = SmartThread(alpha=alpha_t, beta=alpha_t)

    ###########################################################################
    # test_smart_event_set_threads_f1
    ###########################################################################
    def test_smart_event_set_threads_f1(self) -> None:
        """Test set_thread with f1."""

        def my_excepthook(exc_type, exc_value, exc_traceback, thread):
            print(f'in excepthook with args {exc_type}, {exc_value}, '
                  f'{exc_traceback}, {thread}')
            raise Exception(f'{exc_type}, {exc_value}, {exc_traceback}, '
                            f'{thread}')

        threading.excepthook = my_excepthook

        #######################################################################
        # mainline and f1 - mainline sets beta
        #######################################################################
        def f1(s_event, ml_thread):
            print('f1 entered')
            my_c_thread = threading.current_thread()
            assert s_event.alpha_thread is ml_thread
            assert s_event.alpha_thread is alpha_t
            assert s_event.beta_thread is my_c_thread
            assert s_event.beta_thread is threading.current_thread()

            assert s_event.wait()
            time.sleep(1)
            s_event.set()

        alpha_t = threading.current_thread()
        smart_event1 = SmartEvent(alpha=threading.current_thread())
        my_f1_thread = threading.Thread(target=f1,
                                        args=(smart_event1,
                                              threading.current_thread()))
        smart_event1.set_thread(beta=my_f1_thread)
        my_f1_thread.start()

        time.sleep(1)
        smart_event1.set()
        assert smart_event1.wait()

        my_f1_thread.join()

        with pytest.raises(TargetThreadNotAlive):
            smart_event1.set()

        with pytest.raises(TargetThreadNotAlive):
            smart_event1.wait()

        assert smart_event1.alpha_thread is alpha_t
        assert smart_event1.beta_thread is my_f1_thread

        del smart_event1
        del my_f1_thread

        #######################################################################
        # mainline and f2 - f2 sets beta
        #######################################################################

        def f2(s_event, ml_thread):
            print('f2 entered')
            my_c_thread = threading.current_thread()
            s_event.set_thread(beta=my_c_thread)
            assert s_event.alpha_thread is ml_thread
            assert s_event.alpha_thread is alpha_t
            assert s_event.beta_thread is my_c_thread
            assert s_event.beta_thread is threading.current_thread()

            assert s_event.wait()
            time.sleep(1)
            s_event.set()

        smart_event2 = SmartEvent()
        my_f2_thread = threading.Thread(target=f2, args=(smart_event2,
                                                         alpha_t))
        my_f2_thread.start()

        time.sleep(1)
        smart_event2.set()
        assert smart_event2.wait()

        my_f1_thread.join()

        with pytest.raises(TargetThreadNotAlive):
            smart_event2.set()

        with pytest.raises(TargetThreadNotAlive):
            smart_event2.wait()

        assert smart_event2.alpha_thread is alpha_t
        assert smart_event2.beta_thread is my_f2_thread

    ###########################################################################
    # test_smart_event_set_threads_thread_app
    ###########################################################################
    def test_smart_event_set_threads_thread_app(self) -> None:
        """Test set_thread with thread_app."""

        def my_excepthook(exc_type, exc_value, exc_traceback, thread):
            print(f'in excepthook with args {exc_type}, {exc_value}, '
                  f'{exc_traceback}, {thread}')
            raise Exception(f'{exc_type}, {exc_value}, {exc_traceback}, '
                            f'{thread}')

        threading.excepthook = my_excepthook


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
                assert self.s_event.alpha_thread is self.alpha_t1
                assert self.s_event.alpha_thread is alpha_t
                assert self.s_event.beta_thread is self
                my_run_thread = threading.current_thread()
                assert self.s_event.beta_thread is my_run_thread
                assert self.s_event.beta_thread is threading.current_thread()

                assert self.s_event.wait()
                time.sleep(1)
                self.s_event.set()

        alpha_t = threading.current_thread()
        smart_event1 = SmartEvent(alpha=alpha_t)
        my_taa_thread = MyThread(smart_event1, alpha_t)
        smart_event1.set_thread(beta=my_taa_thread)
        my_taa_thread.start()

        time.sleep(1)
        smart_event1.set()
        assert smart_event1.wait()

        my_taa_thread.join()

        with pytest.raises(TargetThreadNotAlive):
            smart_event1.set()

        with pytest.raises(TargetThreadNotAlive):
            smart_event1.wait()

        assert smart_event1.alpha_thread is alpha_t
        assert smart_event1.beta_thread is my_taa_thread

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
                assert self.s_event.alpha_thread is self.alpha_t1
                assert self.s_event.alpha_thread is alpha_t
                assert self.s_event.beta_thread is self
                my_run_thread = threading.current_thread()
                assert self.s_event.beta_thread is my_run_thread
                assert self.s_event.beta_thread is threading.current_thread()

                assert self.s_event.wait()
                time.sleep(1)
                self.s_event.set()

        smart_event2 = SmartEvent()
        smart_event2.set_thread(alpha=alpha_t)
        my_tab_thread = MyThread2(smart_event2, alpha_t)
        my_tab_thread.start()

        time.sleep(1)
        smart_event2.set()
        assert smart_event2.wait()

        my_tab_thread.join()

        with pytest.raises(TargetThreadNotAlive):
            smart_event2.set()

        with pytest.raises(TargetThreadNotAlive):
            smart_event2.wait()

        assert smart_event2.alpha_thread is alpha_t
        assert smart_event2.beta_thread is my_tab_thread

    ###########################################################################
    # test_smart_event_set_threads_thread_event_app
    ###########################################################################
    def test_smart_event_set_threads_thread_event_app(self) -> None:
        """Test set_thread with thread_event_app."""

        def my_excepthook(exc_type, exc_value, exc_traceback, thread):
            print(f'in excepthook with args {exc_type}, {exc_value}, '
                  f'{exc_traceback}, {thread}')
            raise Exception(f'{exc_type}, {exc_value}, {exc_traceback}, '
                            f'{thread}')

        threading.excepthook = my_excepthook

        #######################################################################
        # mainline and ThreadEventApp - mainline sets alpha and beta
        #######################################################################
        class MyThreadEvent1(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self)
                self.alpha_t1 = alpha_t1

            def run(self):
                print('run started')
                assert self.alpha_thread is self.alpha_t1
                assert self.alpha_thread is alpha_t
                assert self.beta_thread is self
                my_run_thread = threading.current_thread()
                assert self.beta_thread is my_run_thread
                assert self.beta_thread is threading.current_thread()

                assert self.wait()
                time.sleep(1)
                self.set()

        alpha_t = threading.current_thread()

        my_te1_thread = MyThreadEvent1(alpha_t)
        my_te1_thread.set_thread(alpha=alpha_t)
        my_te1_thread.set_thread(beta=my_te1_thread)

        assert my_te1_thread.alpha_thread is alpha_t
        assert my_te1_thread.beta_thread is my_ta1_thread

        my_te1_thread.start()

        time.sleep(1)
        my_te1_thread.set()
        assert my_te1_thread.wait()

        my_te1_thread.join()

        with pytest.raises(TargetThreadNotAlive):
            my_te1_thread.set()

        with pytest.raises(TargetThreadNotAlive):
            my_te1_thread.wait()

        assert my_te1_thread.alpha_thread is alpha_t
        assert my_te1_thread.beta_thread is my_te1_thread

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

            def run(self):
                print('run started')
                assert self.alpha_thread is self.alpha_t1
                assert self.alpha_thread is alpha_t
                assert self.beta_thread is self
                my_run_thread = threading.current_thread()
                assert self.beta_thread is my_run_thread
                assert self.beta_thread is threading.current_thread()

                assert self.wait()
                time.sleep(1)
                self.set()

        my_te2_thread = MyThreadEvent2(alpha_t)
        my_te2_thread.set_thread(alpha=alpha_t)
        my_te2_thread.start()

        time.sleep(1)
        my_te2_thread.set()
        assert my_te2_thread.wait()

        my_te2_thread.join()

        with pytest.raises(TargetThreadNotAlive):
            my_te2_thread.set()

        with pytest.raises(TargetThreadNotAlive):
            my_te2_thread.wait()

        assert my_te2_thread.alpha_thread is alpha_t
        assert my_te2_thread.beta_thread is my_te2_thread

        del my_te2_thread

        #######################################################################
        # mainline and ThreadApp - thread_app sets alpha and beta
        #######################################################################
        class MyThreadEvent3(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, alpha=alpha_t)
                self.set_thread(beta=self)
                self.alpha_t1 = alpha_t1

            def run(self):
                print('run started')
                assert self.alpha_thread is self.alpha_t1
                assert self.alpha_thread is alpha_t
                assert self.beta_thread is self
                my_run_thread = threading.current_thread()
                assert self.beta_thread is my_run_thread
                assert self.beta_thread is threading.current_thread()

                assert self.wait()
                time.sleep(1)
                self.set()

        my_te3_thread = MyThreadEvent3(alpha_t)
        my_te3_thread.start()

        time.sleep(1)
        my_te3_thread.set()
        assert my_te3_thread.wait()

        my_te3_thread.join()

        with pytest.raises(TargetThreadNotAlive):
            my_te3_thread.set()

        with pytest.raises(TargetThreadNotAlive):
            my_te3_thread.wait()

        assert my_te3_thread.alpha_thread is alpha_t
        assert my_te3_thread.beta_thread is my_te3_thread

        del my_te3_thread

        #######################################################################
        # mainline and ThreadApp - thread_app sets alpha and beta alternative
        #######################################################################
        class MyThreadEvent4(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, alpha=alpha_t, beta=self)
                self.alpha_t1 = alpha_t1

            def run(self):
                print('run started')
                assert self.alpha_thread is self.alpha_t1
                assert self.alpha_thread is alpha_t
                assert self.beta_thread is self
                my_run_thread = threading.current_thread()
                assert self.beta_thread is my_run_thread
                assert self.beta_thread is threading.current_thread()

                assert self.wait()
                time.sleep(1)
                self.set()

        my_te4_thread = MyThreadEvent4(alpha_t)
        my_te4_thread.start()

        time.sleep(1)
        my_te4_thread.set()
        assert my_te4_thread.wait()

        my_te4_thread.join()

        with pytest.raises(TargetThreadNotAlive):
            my_te4_thread.set()

        with pytest.raises(TargetThreadNotAlive):
            my_te4_thread.wait()

        assert my_te4_thread.alpha_thread is alpha_t
        assert my_te4_thread.beta_thread is my_te4_thread

    ###########################################################################
    # test_smart_event_set_threads_two_f_threads
    ###########################################################################
    def test_smart_event_set_threads_two_f_threads(self) -> None:
        """Test set_thread with thread_event_app."""

        def my_excepthook(exc_type, exc_value, exc_traceback, thread):
            print(f'in excepthook with args {exc_type}, {exc_value}, '
                  f'{exc_traceback}, {thread}')
            raise Exception(f'{exc_type}, {exc_value}, {exc_traceback}, '
                            f'{thread}')

        threading.excepthook = my_excepthook

        #######################################################################
        # two threads - mainline sets alpha and beta
        #######################################################################
        def fa1(s_event):
            logger.debug('fa entered')
            my_fa_thread = threading.current_thread()
            assert s_event.alpha_thread is my_fa_thread

            s_event.wait()
            time.sleep(1)
            s_event.set()

        def fb1(s_event):
            logger.debug('fb entered')
            my_fb_thread = threading.current_thread()
            assert s_event.beta_thread is my_fb_thread

            time.sleep(1)
            s_event.set()
            s_event.wait()

            time.sleep(1)

            with pytest.raises(TargetThreadNotAlive):
                s_event.set()

            with pytest.raises(TargetThreadNotAlive):
                s_event.wait()


        smart_event_ab1 = SmartEvent()
        fa1_thread = threading.Thread(target=fa1, args=(smart_event_ab1,))
        smart_event_ab1.set_thread(alpha=fa1_thread)

        fb1_thread = threading.Thread(target=fb1, args=(smart_event_ab1,))
        smart_event_ab1.set_thread(beta=fb1_thread)

        fa1_thread.start()
        fb1_thread.start()

        fa1_thread.join()
        fb1_thread.join()

        assert smart_event_ab1.alpha_thread is fa1_thread
        assert smart_event_ab1.beta_thread is fb1_thread

        del fa1_thread
        del fb1_thread
        del smart_event_ab1

        #######################################################################
        # two threads - fa2 and fb2 set their own threads
        #######################################################################
        def fa2(s_event):
            logger.debug('fa entered')
            my_fa_thread = threading.current_thread()
            s_event.set_thread(alpha=my_fa_thread)
            assert s_event.alpha_thread is my_fa_thread

            s_event.wait()
            time.sleep(1)
            s_event.set()

        def fb2(s_event):
            logger.debug('fb entered')
            my_fb_thread = threading.current_thread()
            s_event.set_thread(beta=threading.current_thread())
            assert s_event.beta_thread is my_fb_thread

            time.sleep(1)
            s_event.set()
            s_event.wait()

            time.sleep(1)

            with pytest.raises(TargetThreadNotAlive):
                s_event.set()

            with pytest.raises(TargetThreadNotAlive):
                s_event.wait()

        smart_event_ab2 = SmartEvent()
        fa2_thread = threading.Thread(target=fa2, args=(smart_event_ab2,))

        fb2_thread = threading.Thread(target=fb2, args=(smart_event_ab2,))

        fa2_thread.start()
        fb2_thread.start()

        fa2_thread.join()
        fb2_thread.join()

        assert smart_event_ab2.alpha_thread is fa2_thread
        assert smart_event_ab2.beta_thread is fb2_thread

    ###########################################################################
    # test_smart_event_f1_clear
    ###########################################################################
    def test_smart_event_f1_clear(self) -> None:
        """Test smart event timeout with f1 thread."""

        def my_excepthook(exc_type, exc_value, exc_traceback, thread):
            print(f'in excepthook with args {exc_type}, {exc_value}, '
                  f'{exc_traceback}, {thread}')
            raise Exception(f'{exc_type}, {exc_value}, {exc_traceback}, '
                            f'{thread}')

        threading.excepthook = my_excepthook

        def f1(s_event):
            logger.debug('f1 entered')

            start_time = time.time()
            assert s_event.wait()
            duration = time.time() - start_time
            assert 3 <= duration <= 4
            assert not s_event.is_set()

            start_time = time.time()
            assert s_event.wait()
            duration = time.time() - start_time
            assert 3 <= duration <= 4
            assert not s_event.is_set()

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
        assert not smart_event.is_set()

        start_time = time.time()
        assert smart_event.wait()
        duration = time.time() - start_time
        assert 3 <= duration <= 4
        assert not smart_event.is_set()

        beta_thread.join()

    ###########################################################################
    # test_smart_event_thread_app_clear
    ###########################################################################
    def test_smart_event_thread_app_clear(self) -> None:
        """Test smart event timeout with thread_app thread."""

        def my_excepthook(args):
            print(f'in excepthook with args {args}')

        threading.excepthook = my_excepthook

        class MyThread(threading.Thread):
            def __init__(self, s_event: SmartEvent):
                super().__init__()
                self.s_event = s_event
                self.s_event.set_thread(beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                start_time = time.time()
                assert self.s_event.wait()
                duration = time.time() - start_time
                assert 3 <= duration <= 4
                assert not self.s_event.is_set()

                start_time = time.time()
                assert self.s_event.wait()
                duration = time.time() - start_time
                assert 3 <= duration <= 4
                assert not self.s_event.is_set()

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
        assert not smart_event.is_set()

        start_time = time.time()
        assert smart_event.wait()
        duration = time.time() - start_time
        assert 3 <= duration <= 4
        assert not smart_event.is_set()

        thread_app.join()

    ###########################################################################
    # test_smart_event_f1_time_out
    ###########################################################################
    def test_smart_event_f1_time_out(self) -> None:
        """Test smart event timeout with f1 thread."""

        def my_excepthook(exc_type, exc_value, exc_traceback, thread):
            print(f'in excepthook with args {exc_type}, {exc_value}, '
                  f'{exc_traceback}, {thread}')
            raise Exception(f'{exc_type}, {exc_value}, {exc_traceback}, '
                            f'{thread}')

        threading.excepthook = my_excepthook

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
        """Test smart event timeout with thread_app thread."""

        def my_excepthook(args):
            print(f'in excepthook with args {args}')

        threading.excepthook = my_excepthook

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


    ###########################################################################
    # test_smart_event_f1_event_code
    ###########################################################################
    def test_smart_event_f1_event_code(self) -> None:
        """Test smart event code with f1 thread."""

        def my_excepthook(exc_type, exc_value, exc_traceback, thread):
            print(f'in excepthook with args {exc_type}, {exc_value}, '
                  f'{exc_traceback}, {thread}')
            raise Exception(f'{exc_type}, {exc_value}, {exc_traceback}, '
                            f'{thread}')

        threading.excepthook = my_excepthook

        def f1(s_event):
            logger.debug('f1 entered')
            assert s_event.code is None
            assert s_event.wait(timeout=2)
            assert s_event.code == 42
            time.sleep(4)
            s_event.set('forty-two')

        smart_event = SmartEvent(threading.current_thread())
        beta_thread = threading.Thread(target=f1, args=(smart_event,))
        smart_event.set_thread(beta=beta_thread)
        beta_thread.start()
        time.sleep(1)
        smart_event.set(code=42)

        assert smart_event.wait()
        assert smart_event.get_code() == 'forty_two'

        beta_thread.join()

    ###########################################################################
    # test_smart_event_thread_app_event_code
    ###########################################################################
    def test_smart_event_thread_app_event_code(self) -> None:
        """Test smart event code with thread_app thread."""

        def my_excepthook(args):
            print(f'in excepthook with args {args}')

        threading.excepthook = my_excepthook

        class MyThread(threading.Thread):
            def __init__(self, s_event: SmartEvent):
                super().__init__()
                self.s_event = s_event
                self.s_event.set_thread(beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')
                assert self.s_event.get_code() is None
                assert self.s_event.wait(timeout=2)
                assert self.s_event.code == 42
                time.sleep(4)
                self.s_event.set(code='forty-two')

        smart_event = SmartEvent(apha=threading.current_thread())
        thread_app = MyThread(smart_event)
        thread_app.start()

        time.sleep(3)

        smart_event.set(code=42)

        assert smart_event.wait()
        assert smart_event.get_code() == 'forty-two'

        thread_app.join()

    ###########################################################################
    # test_smart_event_thread_event_app_event_code
    ###########################################################################
    def test_smart_event_thread_event_app_event_code(self) -> None:
        """Test smart event code with thread_event_app thread."""

        def my_excepthook(args):
            print(f'in excepthook with args {args}')

        threading.excepthook = my_excepthook

        class MyThread(threading.Thread, SmartEvent):
            def __init__(self,
                         apha: threading.Thread) -> None:
                threading.Thread.__init__(self, alpha=apha)
                SmartEvent.__init__(self, beta_thread=self)

            def run(self):
                logger.debug('ThreadApp run entered')
                assert self.get_code() is None
                assert self.wait(timeout=2)
                assert self.get_code() == 42
                time.sleep(4)
                self.set(code='forty-two')

        thread_event_app = MyThread(alpha=threading.current_thread())
        thread_event_app.start()

        time.sleep(3)

        thread_event_app.set(code=42)

        assert thread_event_app.wait()
        assert thread_event_app.get_code() == 'forty-two'

        thread_event_app.join()

    ###########################################################################
    # test_smart_event_f1_event_logger
    ###########################################################################
    def test_smart_event_f1_event_logger(self, caplog) -> None:
        """Test smart event logger with f1 thread.

        Args:
            caplog: fixture to capture log messages

        """

        def my_excepthook(exc_type, exc_value, exc_traceback, thread):
            print(f'in excepthook with args {exc_type}, {exc_value}, '
                  f'{exc_traceback}, {thread}')
            raise Exception(f'{exc_type}, {exc_value}, {exc_traceback}, '
                            f'{thread}')

        threading.excepthook = my_excepthook

        def f1(s_event):
            logger.debug('f1 entered')
            assert s_event.wait(log_msg='wait for mainline to post 1')
            time.sleep(4)
            s_event.set(log_msg='post mainline 4')

        smart_event = SmartEvent(alpha=threading.current_thread())
        beta_thread = threading.Thread(target=f1, args=(smart_event,))
        smart_event.set_thread(beta=beta_thread)
        beta_thread.start()
        time.sleep(1)
        smart_event.set(log_msg=f'post thread {beta_thread.name} 2')

        assert smart_event.wait(log_msg='wait for post from thread 3')

        beta_thread.join()

        log_found = 0
        for record in caplog.records:
            if record.msg == 'wait for mainline to post 1':
                log_found += 1

        assert log_found == 1

    ###########################################################################
    # test_smart_event_thread_app_event_logger
    ###########################################################################
    def test_smart_event_thread_app_event_logger(self) -> None:
        """Test smart event logger with thread_app thread."""

        def my_excepthook(args):
            print(f'in excepthook with args {args}')

        threading.excepthook = my_excepthook

        class MyThread(threading.Thread):
            def __init__(self, s_event: SmartEvent):
                super().__init__()
                self.s_event = s_event
                self.s_event.set_thread(beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')
                assert self.s_event.wait(log_msg='wait for mainline to post 1')
                time.sleep(4)
                self.s_event.set(log_msg='post mainline 4')

        smart_event = SmartEvent(alpha=threading.current_thread())
        thread_app = MyThread(smart_event)
        thread_app.start()

        time.sleep(3)

        smart_event.set(log_msg=f'post thread {beta_thread.name} 2')

        assert smart_event.wait(log_msg='wait for post from thread 3')

        thread_app.join()

    ###########################################################################
    # test_smart_event_thread_event_app_event_logger
    ###########################################################################
    def test_smart_event_thread_event_app_event_logger(self) -> None:
        """Test smart event logger with thread_event_app thread."""

        def my_excepthook(args):
            print(f'in excepthook with args {args}')

        threading.excepthook = my_excepthook

        class MyThread(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, alpha=alpha, beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')
                assert self.wait(log_msg='wait for mainline to post 1')
                time.sleep(4)
                self.set(log_msg='post mainline 4')

        thread_event_app = MyThread(alpha=threading.current_thread())
        thread_event_app.start()

        time.sleep(3)

        thread_event_app.set(log_msg=f'post thread {beta_thread.name} 2')

        assert thread_event_app.wait(log_msg='wait for post from thread 3')

        thread_event_app.join()

    ###########################################################################
    # test_smart_event_thread_app_combos
    ###########################################################################
    def test_smart_event_thread_app_combos(self,
                                           action1_arg: Any,
                                           msg_arg1: Any,
                                           num_msg1_arg: int,
                                           action2_arg: Any,
                                           msg_arg2: Any,
                                           num_msg2_arg: int
                                           ) -> None:
        """Test the SmartEvent with ThreadApp combos.

        Args:
            action1_arg: the action to do for first batch
            msg_arg1: the messages to be sent for first batch
            num_msg1_arg: the number of messages to be sent for first batch
            action2_arg: the action to do for second batch
            msg_arg2: the messages to be sent for second batch
            num_msg2_arg: the number of messages to be sent for second batch

        Raises:
            IncorrectActionSpecified: The Action is not recognized

        """




        def get_exp_recv_msg(msg) -> Any:
            """Return the expected recv msg give the send msg.

            Args:
                msg: msg that is sent

            Returns:
                msg to be used to verify what was received

            Raises:
                UnrecognizedMessageType: The message type is not int, str,
                                         or float
            """
            if isinstance(msg, int):
                return msg * 10

            if isinstance(msg, str):
                ret_value = 0
                for letter in msg:
                    ret_value += ord(letter)
                return ret_value

            if isinstance(msg, float):
                return math.ceil(msg) + 10

            raise UnrecognizedMessageType('The message type is not int, str,'
                                          'or float')

        class SmartEventApp(threading.Thread):
            def __init__(self,
                         action_event: threading.Event,
                         complete_event: threading.Event) -> None:
                super().__init__()
                self.smart_event = SmartEvent()
                self.action_event = action_event
                self.action_to_do = [0]
                self.complete_event = complete_event
                self.msgs = [0]
                self.exc = None

            def run(self):
                """Thread to send and receive messages.

                Raises:
                    UnrecognizedActionToDo: SmartEventApp received an
                                              unrecognized action
                """
                try:
                    logger.debug('SmartEventApp run started')
                    self.smart_event.set_child_thread_id()
                    while True:
                        logger.debug('SmartEventApp about to wait on action '
                                     'event')
                        self.action_event.wait()
                        self.action_event.clear()
                        if self.action_to_do[0] == 'send':
                            logger.debug('SmartEventApp doing send')
                            for msg in self.msgs:
                                self.smart_event.send(msg)
                                logger.debug('SmartEventApp sent '
                                             f'message {msg}')
                            self.complete_event.set()
                        elif self.action_to_do[0] == 'pause_send':
                            logger.debug('SmartEventApp doing pause_send')
                            time.sleep(1)
                            for msg in self.msgs:
                                self.smart_event.send(msg)
                                logger.debug('SmartEventApp sent '
                                             f'message {msg}')
                            self.complete_event.set()
                        elif self.action_to_do[0] == 'recv_reply':
                            logger.debug('SmartEventApp doing recv_reply')
                            logger.debug('SmartEventApp msgs = '
                                         f'{self.msgs}')
                            for msg in self.msgs:
                                recv_msg = self.smart_event.recv()
                                logger.debug('SmartEventApp received message '
                                             f'{recv_msg}')
                                assert recv_msg == msg
                                reply_msg = get_exp_recv_msg(msg)
                                self.smart_event.send(reply_msg)
                            self.complete_event.set()
                        elif self.action_to_do[0] == 'recv_verify':
                            logger.debug('SmartEventApp doing recv_verify')
                            for msg in self.msgs:
                                recv_msg = self.smart_event.recv()
                                logger.debug('SmartEventApp received message '
                                             f'{recv_msg}')
                                test_msg = get_exp_recv_msg(msg)
                                assert recv_msg == test_msg
                            self.complete_event.set()
                        elif self.action_to_do[0] == 'send_recv':
                            logger.debug('SmartEventApp doing send_recv')
                            for msg in self.msgs:
                                recv_msg = self.smart_event.send_recv(msg)
                                exp_recv_msg = get_exp_recv_msg(msg)
                                assert recv_msg == exp_recv_msg
                            self.complete_event.set()
                        elif self.action_to_do[0] == 'exit':
                            logger.debug('SmartEventApp doing exit')
                            break
                        else:
                            raise UnrecognizedActionToDo('SmartEventApp '
                                                         'received an '
                                                         'unrecognized action')
                except Exception as e:
                    self.exc = e

            def send_msg(self, msg):
                """Send message.

                Args:
                    msg: message to send
                """
                self.smart_event.send(msg)

            def recv_msg(self) -> Any:
                """Receive message.

                Returns:
                    message received
                """
                return self.smart_event.recv()

            def send_recv_msg(self, msg) -> Any:
                """Send message and receive response.

                Args:
                    msg: message to send

                Returns:
                    message received
                """
                return self.smart_event.send_recv(msg)

        def f1(in_smart_event: SmartEvent,
               action_event: threading.Event,
               action_to_do: List[Any],
               complete_event: threading.Event,
               msgs: List[Any],
               exc1: List[Any]) -> None:
            """Thread to send or receive messages.

            Args:
                in_smart_event: instance of SmartEvent class
                action_event: event to wait on for action to perform
                action_to_do: send, recv, send_recv, or done
                complete_event: event to set when done with action
                msgs: list of message that are to be sent
                exc1: list to be set with exception

            Raises:
                UnrecognizedActionToDo: Thread received an unrecognized action
                Exception: any exception in thread
            """
            try:
                logger.debug('thread f1 started')
                while True:
                    logger.debug('thread f1 about to wait on action event')
                    action_event.wait()
                    action_event.clear()
                    if action_to_do[0] == 'send':
                        logger.debug('thread f1 doing send')
                        for msg in msgs:
                            in_smart_event.send(msg)
                            logger.debug(f'thread f1 sent message {msg}')
                        complete_event.set()
                    elif action_to_do[0] == 'pause_send':
                        logger.debug('thread f1 doing pause_send')
                        time.sleep(1)
                        for msg in msgs:
                            in_smart_event.send(msg)
                            logger.debug(f'thread f1 sent message {msg}')
                        complete_event.set()
                    elif action_to_do[0] == 'recv_reply':
                        logger.debug('thread f1 doing recv_reply')
                        logger.debug(f'thread f1 msgs = {msgs}')
                        for msg in msgs:
                            recv_msg = in_smart_event.recv()
                            logger.debug('thread f1 received message '
                                         f'{recv_msg}')
                            assert recv_msg == msg
                            reply_msg = get_exp_recv_msg(msg)
                            in_smart_event.send(reply_msg)
                        complete_event.set()
                    elif action_to_do[0] == 'recv_verify':
                        logger.debug('thread f1 doing recv_verify')
                        for msg in msgs:
                            recv_msg = in_smart_event.recv()
                            logger.debug('thread f1 received message '
                                         f'{recv_msg}')
                            test_msg = get_exp_recv_msg(msg)
                            assert recv_msg == test_msg
                        complete_event.set()
                    elif action_to_do[0] == 'send_recv':
                        logger.debug('thread f1 doing send_recv')
                        for msg in msgs:
                            recv_msg = in_smart_event.send_recv(msg)
                            exp_recv_msg = get_exp_recv_msg(msg)
                            assert recv_msg == exp_recv_msg
                        complete_event.set()
                    elif action_to_do[0] == 'exit':
                        logger.debug('thread f1 doing exit')
                        break
                    else:
                        raise UnrecognizedActionToDo('Thread received an '
                                                     'unrecognized action')
            except Exception as f1_e:
                exc1[0] = f1_e

        smart_event = SmartEvent()
        thread_action_event = SmartEvent()  # threading.Event()
        thread_actions = [0]
        thread_complete_event = SmartEvent()  # threading.Event()
        send_msgs = [0]
        exc = [None]

        f1_thread = threading.Thread(target=f1,
                                     args=(smart_event,
                                           thread_action_event,
                                           thread_actions,
                                           thread_complete_event,
                                           send_msgs,
                                           exc))

        logger.debug('main about to start f1 thread')
        f1_thread.start()

        logger.debug('main about to start SmartEventApp')
        app_action_event = threading.Event()
        app_complete_event = threading.Event()
        smart_event_app = SmartEventApp(app_action_event, app_complete_event)
        smart_event_app.start()

        super_msgs = []
        msg_list = []
        for i in range(num_msg1_arg):
            msg_list.append(msg_arg1[i])
        super_msgs.append(msg_list)
        msg_list = []
        for i in range(num_msg2_arg):
            msg_list.append(msg_arg2[i])
        super_msgs.append(msg_list)
        logger.debug(f'main super_msgs {super_msgs}')

        #######################################################################
        # action loop
        #######################################################################
        actions = []
        actions.append(action1_arg)
        actions.append(action2_arg)
        for action in actions:
            _ = send_msgs.pop(0)
            send_msgs.extend(super_msgs.pop(0))
            smart_event_app.msgs = send_msgs
            if action == Action.MainSend:
                logger.debug('main starting Action.MainSend')
                logger.debug(f'main send_msgs = {send_msgs}')
                for msg in send_msgs:
                    logger.debug(f'main sending msg {msg}')
                    smart_event.send(msg)
                    smart_event_app.send_msg(msg)
                thread_actions[0] = 'recv_reply'
                thread_action_event.set()
                smart_event_app.action_to_do[0] = 'recv_reply'
                smart_event_app.action_event.set()
                if exc[0]:
                    raise exc[0]
                if smart_event_app.exc:
                    raise smart_event_app.exc
                for msg in send_msgs:
                    exp_recv_msg = get_exp_recv_msg(msg)
                    recv_msg = smart_event.recv()
                    assert recv_msg == exp_recv_msg
                    recv_msg = smart_event_app.recv_msg()
                    assert recv_msg == exp_recv_msg
                thread_complete_event.wait()
                thread_complete_event.clear()
                smart_event_app.complete_event.wait()
                smart_event_app.complete_event.clear()
            elif action == Action.MainRecv:
                logger.debug('main starting Action.MainRecv')
                thread_actions[0] = 'pause_send'
                thread_action_event.set()
                smart_event_app.action_to_do[0] = 'pause_send'
                smart_event_app.action_event.set()
                if exc[0]:
                    raise exc[0]
                if smart_event_app.exc:
                    raise smart_event_app.exc
                for msg in send_msgs:
                    recv_msg = smart_event.recv()
                    assert recv_msg == msg
                    recv_msg = smart_event_app.recv_msg()
                    assert recv_msg == msg
                    reply_msg = get_exp_recv_msg(msg)
                    smart_event.send(reply_msg)
                    smart_event_app.send_msg(reply_msg)
                thread_complete_event.wait()
                thread_complete_event.clear()
                smart_event_app.complete_event.wait()
                smart_event_app.complete_event.clear()
                thread_actions[0] = 'recv_verify'
                thread_action_event.set()
                smart_event_app.action_to_do[0] = 'recv_verify'
                smart_event_app.action_event.set()
                thread_complete_event.wait()
                thread_complete_event.clear()
                smart_event_app.complete_event.wait()
                smart_event_app.complete_event.clear()
            elif action == Action.ThreadSend:
                logger.debug('main starting Action.ThreadSend')
                thread_actions[0] = 'send'
                thread_action_event.set()
                smart_event_app.action_to_do[0] = 'send'
                smart_event_app.action_event.set()
                time.sleep(1)
                if exc[0]:
                    raise exc[0]
                if smart_event_app.exc:
                    raise smart_event_app.exc
                for msg in send_msgs:
                    recv_msg = smart_event.recv()
                    assert recv_msg == msg
                    recv_msg = smart_event_app.recv_msg()
                    assert recv_msg == msg
                    reply_msg = get_exp_recv_msg(msg)
                    smart_event.send(reply_msg)
                    smart_event_app.send_msg(reply_msg)
                thread_complete_event.wait()
                thread_complete_event.clear()
                smart_event_app.complete_event.wait()
                smart_event_app.complete_event.clear()
                thread_actions[0] = 'recv_verify'
                thread_action_event.set()
                smart_event_app.action_to_do[0] = 'recv_verify'
                smart_event_app.action_event.set()
                thread_complete_event.wait()
                thread_complete_event.clear()
                smart_event_app.complete_event.wait()
                smart_event_app.complete_event.clear()
            elif action == Action.ThreadRecv:
                logger.debug('main starting Action.ThreadRecv')
                thread_actions[0] = 'recv_reply'
                thread_action_event.set()
                smart_event_app.action_to_do[0] = 'recv_reply'
                smart_event_app.action_event.set()
                time.sleep(1)
                if exc[0]:
                    raise exc[0]
                if smart_event_app.exc:
                    raise smart_event_app.exc
                for msg in send_msgs:
                    smart_event.send(msg)
                    smart_event_app.send_msg(msg)
                for msg in send_msgs:
                    exp_recv_msg = get_exp_recv_msg(msg)
                    recv_msg = smart_event.recv()
                    assert recv_msg == exp_recv_msg
                    recv_msg = smart_event_app.recv_msg()
                    assert recv_msg == exp_recv_msg
                thread_complete_event.wait()
                thread_complete_event.clear()
                smart_event_app.complete_event.wait()
                smart_event_app.complete_event.clear()
            elif action == Action.MainSendRecv:
                logger.debug('main starting Action.MainSendRecv')
                thread_actions[0] = 'recv_reply'
                thread_action_event.set()
                smart_event_app.action_to_do[0] = 'recv_reply'
                smart_event_app.action_event.set()
                if exc[0]:
                    raise exc[0]
                if smart_event_app.exc:
                    raise smart_event_app.exc
                for msg in send_msgs:
                    exp_recv_msg = get_exp_recv_msg(msg)
                    recv_msg = smart_event.send_recv(msg)
                    assert recv_msg == exp_recv_msg
                    recv_msg = smart_event_app.send_recv_msg(msg)
                    assert recv_msg == exp_recv_msg
                thread_complete_event.wait()
                thread_complete_event.clear()
                smart_event_app.complete_event.wait()
                smart_event_app.complete_event.clear()
            elif action == Action.ThreadSendRecv:
                logger.debug('main starting Action.ThreadSendRecv')
                thread_actions[0] = 'send_recv'
                thread_action_event.set()
                smart_event_app.action_to_do[0] = 'send_recv'
                smart_event_app.action_event.set()
                time.sleep(1)
                if exc[0]:
                    raise exc[0]
                if smart_event_app.exc:
                    raise smart_event_app.exc
                for msg in send_msgs:
                    recv_msg = smart_event.recv()
                    assert recv_msg == msg
                    recv_msg = smart_event_app.recv_msg()
                    assert recv_msg == msg
                    reply_msg = get_exp_recv_msg(msg)
                    smart_event.send(reply_msg)
                    smart_event_app.send_msg(reply_msg)
                thread_complete_event.wait()
                thread_complete_event.clear()
                smart_event_app.complete_event.wait()
                smart_event_app.complete_event.clear()
            else:
                raise IncorrectActionSpecified('The Action is not recognized')

        logger.debug('main completed all actions')
        thread_actions[0] = 'exit'
        thread_action_event.set()
        f1_thread.join()
        if exc[0]:
            raise exc[0]

        smart_event_app.action_to_do[0] = 'exit'
        smart_event_app.action_event.set()
        smart_event_app.join()
        if smart_event_app.exc:
            raise smart_event_app.exc
