"""test_thread_comm.py module."""

import pytest
import time
from typing import Any, cast, Union

import threading
from scottbrian_utils.diag_msg import diag_msg
from scottbrian_utils.thread_comm import ThreadComm


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
requests_arg_list = [1, 2, 3, 10, 33]


@pytest.fixture(params=requests_arg_list)  # type: ignore
def requests_arg(request: Any) -> int:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


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
    # test_thread_comm
    ###########################################################################
    def test_thread_comm(self) -> None:
        """Test the ThreadComm."""
        thread_comm = ThreadComm()
        a_code = 42
        inner_wait_time = 7

        b_code = 17
        outer_wait_time = 4

        def f1(in_thread_comm: ThreadComm,
               exp_code: int,
               exp_wait_time: int,
               code2: int,
               wait_time: int):
            entry_time = time.time()
            diag_msg('about to recv msg')
            msg = in_thread_comm.recv(timeout=5)
            print(f'f1 received message {msg}')
            assert msg == exp_code
            assert time.time() - entry_time >= exp_wait_time
            time.sleep(wait_time)
            # in_thread_comm.send(code2)

        f1_thread = threading.Thread(target=f1,
                                     args=(thread_comm,
                                           a_code,
                                           outer_wait_time,
                                           b_code,
                                           inner_wait_time))
        f1_thread.run()
        time.sleep(outer_wait_time)
        diag_msg('about to send msg')
        thread_comm.send(a_code, timeout=3)
        start_time = time.time()
        # msg = thread_comm.recv()
        # assert msg == b_code
        # assert time.time() - start_time >= inner_wait_time

    ###########################################################################
    # repr for ThreadComm
    ###########################################################################
    def test_thread_comm_repr(self) -> None:
        """test event with code repr."""
        thread_comm = ThreadComm()

        expected_repr_str = 'ThreadComm()'

        assert repr(a_event) == expected_repr_str
