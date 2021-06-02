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
# requests_arg fixture
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
    # test_thread_comm_simple_send
    ###########################################################################
    def test_thread_comm_simple_send(self,
                                     msg_arg: Any
                                     ) -> None:
        """Test the ThreadComm."""
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
        diag_msg(f'main about to send msg {msg_arg}')
        thread_comm.send(msg_arg)
        f1_thread.join()
        if exc[0]:
            raise exc[0]

    ###########################################################################
    # test_thread_comm_simple_send
    ###########################################################################
    def test_thread_comm_simple_send2(self,
                                      msg_arg: Any
                                      ) -> None:
        """Test the ThreadComm."""
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
                    self._run()
                except AssertionError as e:
                    self.exc = e

            def _run(self):
                """Thread to receive message."""
                logger.debug('thread f1 about to recv msg')
                msg = self.thread_comm.recv()
                logger.debug(f'thread f1 received message {msg}')
                assert msg == self.exp_msg

            def send_msg(self):
                self.thread_comm.send(self.exp_msg)

        logger.debug('main about to start f1 thread')
        thread_comm_app = ThreadCommApp(msg_arg)
        thread_comm_app.start()
        diag_msg(f'main about to send msg {msg_arg}')
        thread_comm_app.send_msg()
        thread_comm_app.join()
        if thread_comm_app.exc:
            raise thread_comm_app.exc

    ###########################################################################
    # repr for ThreadComm
    ###########################################################################
    def test_thread_comm_repr(self) -> None:
        """test event with code repr."""
        thread_comm = ThreadComm()

        expected_repr_str = 'ThreadComm()'

        assert repr(a_event) == expected_repr_str
