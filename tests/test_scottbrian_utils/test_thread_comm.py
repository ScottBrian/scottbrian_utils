"""test_thread_comm.py module."""


import pytest
import time
from typing import Any, cast, List, Union

import threading
from scottbrian_utils.diag_msg import diag_msg
from scottbrian_utils.thread_comm import ThreadComm

import logging

logger = logging.getLogger(__name__)
logger.debug('about to start the tests')

# ###############################################################################
# # Throttle test exceptions
# ###############################################################################
# class ErrorTstThrottle(Exception):
#     """Base class for exception in this module."""
#     pass
#
#
# class InvalidRouteNum(ErrorTstThrottle):
#     """InvalidRouteNum exception class."""
#     pass
#
#
# class InvalidModeNum(ErrorTstThrottle):
#     """InvalidModeNum exception class."""
#     pass
###############################################################################
# msg_arg fixture
###############################################################################
msg_arg_list = [1, 2, 3, 'a', 'bb', 'xyz', 0.1, 0.2, 0.33, 'word to the wise']


@pytest.fixture(params=msg_arg_list)  # type: ignore
def msg_arg(request: Any) -> Any:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param

###############################################################################
# reply_arg fixture
###############################################################################
reply_arg_list = [12, 23, 34, 's', 'tt', 'abc', 3.1, 3.2, 3.33,
                  'penny for your thoughts']


@pytest.fixture(params=reply_arg_list)  # type: ignore
def reply_arg(request: Any) -> Any:
    """Using different reply messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param
###############################################################################
# seconds_arg fixture
###############################################################################
seconds_arg_list = [0.1, 0.2, 0.3, 1, 2, 3, 3.3, 9]


@pytest.fixture(params=seconds_arg_list)  # type: ignore
def seconds_arg(request: Any) -> Union[int, float]:
    """Using different seconds.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(Union[int, float], request.param)


###############################################################################
# mode_arg fixture
###############################################################################
lb_threshold_arg_list = [0.1, 1, 1.5, 2, 3]


@pytest.fixture(params=lb_threshold_arg_list)  # type: ignore
def lb_threshold_arg(request: Any) -> Union[int, float]:
    """Using different lb_threshold values.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(Union[int, float], request.param)


###############################################################################
# early_count_arg fixture
###############################################################################
early_count_arg_list = [1, 2, 3]


@pytest.fixture(params=early_count_arg_list)  # type: ignore
def early_count_arg(request: Any) -> int:
    """Using different early_count values.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# send_interval_mult_arg fixture
###############################################################################
send_interval_mult_arg_list = [0.0, 0.1, 0.2, 0.3, 0.5, 0.9, 1.0, 1.1, 1.5]


@pytest.fixture(params=send_interval_mult_arg_list)  # type: ignore
def send_interval_mult_arg(request: Any) -> float:
    """Using different send rates.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(float, request.param)


###############################################################################
# TestThreadCommBasic class to test ThreadComm methods
###############################################################################
class TestThreadCommBasic:

    ###########################################################################
    # test_thread_comm_simple_main_send
    ###########################################################################
    def test_thread_comm_simple_main_send(self,
                                     msg_arg: Any
                                     ) -> None:
        """Test the ThreadComm with main send.

        Args:
            msg_arg: the message to be send by main

        """
        def f1(in_thread_comm: ThreadComm,
               exp_msg: int,
               exc1: List[Any]) -> None:
            """Thread to receive message."""
            logger.debug('thread f1 about to recv msg')
            msg = in_thread_comm.recv()
            logger.debug(f'thread f1 received message {msg}')
            try:
                assert msg == exp_msg
            except AssertionError as e:
                exc1[0] = e

        thread_comm = ThreadComm()
        exc = [None]

        f1_thread = threading.Thread(target=f1,
                                     args=(thread_comm,
                                           msg_arg,
                                           exc))

        logger.debug('main about to start f1 thread')
        f1_thread.start()
        logger.debug(f'main about to send msg {msg_arg}')
        thread_comm.send(msg_arg)
        f1_thread.join()
        if exc[0]:
            raise exc[0]

    ###########################################################################
    # test_thread_comm_simple_main_send2
    ###########################################################################
    def test_thread_comm_simple_main_send2(self,
                                      msg_arg: Any
                                      ) -> None:
        """Test the ThreadComm with main send2.

        Args:
            msg_arg: the message to be send by main

        """
        class ThreadCommApp(threading.Thread):
            def __init__(self,
                         exp_msg: Any) -> None:
                super().__init__()
                self.thread_comm = ThreadComm()
                self.exp_msg = exp_msg
                self.exc = None

            def run(self):
                """Thread to receive message."""
                try:
                    logger.debug('thread f1 about to recv msg')
                    msg = self.thread_comm.recv()
                    logger.debug(f'thread f1 received message {msg}')
                    assert msg == self.exp_msg
                except Exception as e:
                    self.exc = e

            def send_msg(self):
                self.thread_comm.send(self.exp_msg)

        logger.debug('main about to start f1 thread')
        thread_comm_app = ThreadCommApp(msg_arg)
        thread_comm_app.start()
        logger.debug(f'main about to send msg {msg_arg}')
        thread_comm_app.send_msg()
        thread_comm_app.join()
        if thread_comm_app.exc:
            raise thread_comm_app.exc

    ###########################################################################
    # test_thread_comm_simple_main_recv
    ###########################################################################
    def test_thread_comm_simple_main_recv(self,
                                          msg_arg: Any
                                          ) -> None:
        """Test the ThreadComm with main recv.

        Args:
            msg_arg: the message to be send by thread

        """
        def f1(in_thread_comm: ThreadComm,
                msg: int) -> None:
            """Thread to receive message."""
            logger.debug('thread f1 about to send msg')
            in_thread_comm.send(msg)
            logger.debug(f'thread f1 sent message {msg}')


        thread_comm = ThreadComm()

        f1_thread = threading.Thread(target=f1,
                                     args=(thread_comm,
                                           msg_arg))

        logger.debug('main about to start f1 thread')
        try:
            f1_thread.start()
            logger.debug(f'main about to receive msg from thread')
            msg_received = thread_comm.recv()
            f1_thread.join()
            assert msg_received == msg_arg
        except Exception as e:
            logger.exception(f'exception {e!r}')
            raise

    ###########################################################################
    # test_thread_comm_simple_main_recv2
    ###########################################################################
    def test_thread_comm_simple_main_recv2(self,
                                           msg_arg: Any
                                           ) -> None:
        """Test the ThreadComm with main recv.

        Args:
            msg_arg: the message to be send by thread

        """
        class ThreadCommApp(threading.Thread):
            def __init__(self,
                         msg: Any) -> None:
                super().__init__()
                self.thread_comm = ThreadComm()
                self.msg = msg
                self.exc = None

            def run(self):
                """Thread to receive message."""
                try:
                    logger.debug('thread f1 about to send msg')
                    self.thread_comm.send(self.msg)
                    logger.debug(f'thread f1 sent message {self.msg}')
                except Exception as e:
                    self.exc = e

            def recv_msg(self):
                return self.thread_comm.recv()

        logger.debug('main about to start f1 thread')
        thread_comm_app = ThreadCommApp(msg_arg)
        thread_comm_app.start()
        logger.debug(f'main about to receive msg from thread')
        received_msg = thread_comm_app.recv_msg()
        thread_comm_app.join()
        if thread_comm_app.exc:
            raise thread_comm_app.exc

        assert received_msg == msg_arg

    ###########################################################################
    # test_thread_comm_simple_main_send_recv
    ###########################################################################
    def test_thread_comm_simple_main_send_recv(self,
                                          msg_arg: Any,
                                          reply_arg: Any
                                          ) -> None:
        """Test the ThreadComm with main send_recv.

        Args:
            msg_arg: the message to be send by main

        """
        def f1(in_thread_comm: ThreadComm,
                exp_msg: Any,
                reply: Any,
                exc1: List[Any]) -> None:
            """Thread to receive and send reply message."""
            try:
                logger.debug('thread f1 about to recv msg')
                msg = in_thread_comm.recv()
                assert msg == 1 # exp_msg
                logger.debug(f'thread f1 received message {msg}')
                logger.debug(f'thread f1 about to send reply {reply}')
                in_thread_comm.send(reply)
                logger.debug(f'thread f1 sent replay {reply}')
            except Exception as e:
                exc1[0] = e


        thread_comm = ThreadComm()
        exc = [None]

        f1_thread = threading.Thread(target=f1,
                                     args=(thread_comm,
                                           msg_arg,
                                           reply_arg,
                                           exc))

        logger.debug('main about to start f1 thread')
        try:
            f1_thread.start()
            logger.debug(f'main about to send msg {msg_arg} to thread and '
                         f'receive reply')
            msg_received = thread_comm.send_recv(msg_arg)
            assert msg_received == reply_arg
            f1_thread.join()
            if exc[0]:
                raise exc[0]
        except Exception as e:
            logger.exception(f'exception {e!r}')
            raise

    ###########################################################################
    # test_thread_comm_simple_main_recv2
    ###########################################################################
    def test_thread_comm_simple_main_send_recv2(self,
                                           msg_arg: Any,
                                           reply_arg: Any
                                           ) -> None:
        """Test the ThreadComm with main recv.

        Args:
            msg_arg: the message to be send by thread

        """
        class ThreadCommApp(threading.Thread):
            def __init__(self,
                         msg: Any) -> None:
                super().__init__()
                self.thread_comm = ThreadComm()
                self.msg = msg
                self.exc = None

            def run(self):
                """Thread to receive message."""
                try:
                    logger.debug('thread f1 about to send msg')
                    self.thread_comm.send(self.msg)
                    logger.debug(f'thread f1 sent message {self.msg}')
                except Exception as e:
                    self.exc = e

            def recv_msg(self):
                return self.thread_comm.recv()

        logger.debug('main about to start f1 thread')
        thread_comm_app = ThreadCommApp(msg_arg)
        thread_comm_app.start()
        logger.debug(f'main about to receive msg from thread')
        received_msg = thread_comm_app.recv_msg()
        thread_comm_app.join()
        if thread_comm_app.exc:
            raise thread_comm_app.exc

        assert received_msg == msg_arg

    ###########################################################################
    # repr for ThreadComm
    ###########################################################################
    def test_thread_comm_repr(self) -> None:
        """test event with code repr."""
        thread_comm = ThreadComm()

        expected_repr_str = 'ThreadComm(max_msgs=16)'

        assert repr(thread_comm) == expected_repr_str
