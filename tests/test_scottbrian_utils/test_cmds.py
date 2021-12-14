"""test_cmds.py module."""

########################################################################
# Standard Library
########################################################################
import logging
import queue
import re
import threading
import time
import traceback
from typing import Any, cast, Optional, Union

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.cmds import Cmds, GetCmdTimedOut

########################################################################
# type aliases
########################################################################
OptIntFloat = Optional[Union[int, float]]

########################################################################
# Set up logging
########################################################################
logger = logging.getLogger(__name__)
logger.debug('about to start the tests')


##############################################################################
# Cmds test exceptions
###############################################################################
class ErrorTstCmds(Exception):
    """Base class for exception in this module."""
    pass


class InvalidRouteNum(ErrorTstCmds):
    """InvalidRouteNum exception class."""
    pass


class InvalidModeNum(ErrorTstCmds):
    """InvalidModeNum exception class."""
    pass


class BadRequestStyleArg(ErrorTstCmds):
    """BadRequestStyleArg exception class."""
    pass


class IncorrectWhichTimer(ErrorTstCmds):
    """IncorrectWhichTimer exception class."""
    pass


###############################################################################
# timeout_arg fixture
###############################################################################
timeout_arg_list = [0.0, 0.3, 0.5, 1, 2, 4]


@pytest.fixture(params=timeout_arg_list)  # type: ignore
def timeout_arg(request: Any) -> float:
    """Using different seconds for timeout.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(float, request.param)


###############################################################################
# TestCmdsBasic class to test Cmds methods
###############################################################################
class TestCmdsErrors:
    """TestCmdsErrors class."""
    def test_cmds_timeout(self,
                          timeout_arg: float) -> None:
        """test_cmds_timeout.

        Args:
            timeout_arg: number of seconds to use for timeout value
                           on get_cmd request

        """
        def f1():
            logger.debug('f1 beta entered')
            f1_to_low = f1_timeout * .9
            f1_to_high = f1_timeout * 1.1

            f1_cmds = Cmds()

            logger.debug('f1 beta starting timeout -1')
            f1_cmds.start_clock(clock_iter=1)
            cmds.get_cmd('beta', timeout=-1)
            assert f1_to_low <= f1_cmds.duration() <= f1_to_high

            logger.debug('f1 beta starting timeout 0')
            f1_cmds.start_clock(clock_iter=2)
            cmds.get_cmd('beta', timeout=0)
            assert f1_to_low <= f1_cmds.duration() <= f1_to_high

            logger.debug('f1 beta starting timeout None')
            f1_cmds.start_clock(clock_iter=3)
            cmds.get_cmd('beta', timeout=None)
            assert f1_to_low <= f1_cmds.duration() <= f1_to_high

            logger.debug('f1 beta exiting')

        logger.debug('mainline entered')
        cmds = Cmds()
        f1_timeout = 5
        f1_thread = threading.Thread(target=f1)

        # we will try -1 as a timeout value in the section below, and
        # we also use the -1 value to do the default value
        if timeout_arg == 0.0:  # if do default timeout
            ############################################################
            # get_cmd timeout with default
            ############################################################
            to_low = Cmds.GET_CMD_TIMEOUT * .9
            to_high = Cmds.GET_CMD_TIMEOUT * 1.1
            cmds.start_clock(clock_iter=1)
            with pytest.raises(GetCmdTimedOut):
                _ = cmds.get_cmd('beta')
            assert to_low <= cmds.duration() <= to_high

            f1_thread.start()
            logger.debug(f'mainline starting timeout loop')
            for idx in range(2, 5):  # 2, 3, 4
                logger.debug(f'mainline starting timeout loop {idx}')
                cmds.start_clock(clock_iter=idx)
                cmds.pause(seconds=f1_timeout, clock_iter=idx)
                logger.debug(f'mainline duration {cmds.duration()}')
                cmds.queue_cmd('beta')

        else:
            ############################################################
            # get_cmd timeout with timeout_arg
            ############################################################
            to_low = timeout_arg * .9
            to_high = timeout_arg * 1.1
            logger.debug(f'mainline starting timeout {timeout_arg}')
            cmds.start_clock(clock_iter=1)
            with pytest.raises(GetCmdTimedOut):
                _ = cmds.get_cmd('beta', timeout_arg)
            assert to_low <= cmds.duration() <= to_high

        logger.debug('mainline entered')

###############################################################################
# TestTimerBasic class to test Timer methods
###############################################################################
class TestTimerBasic:
    """Test basic functions of Timer."""

    ###########################################################################
    # test_timer_example1
    ###########################################################################
    def test_timer_example(self) -> None:
        """Test timer example."""

        # create a timer and use in a loop
        print('mainline entered')
        timer = Timer(timeout=3)
        for idx in range(10):
            print(f'idx = {idx}')
            time.sleep(1)
            if timer.is_expired():
                print('timer has expired')
            break
        print('mainline exiting')


    ###########################################################################
    # repr with mode async
    ###########################################################################
    # def test_timer_repr(self,
    #                              requests_arg: int,
    #                              seconds_arg: Union[int, float]
    #                              ) -> None:
    #     """test_timer repr mode 1 with various requests and seconds.
    #
    #     Args:
    #         requests_arg: fixture that provides args
    #         seconds_arg: fixture that provides args
    #
    #     """
    #     #######################################################################
    #     # throttle with async_q_size specified
    #     #######################################################################
    #     a_throttle = Timer(requests=requests_arg,
    #                           seconds=seconds_arg,
    #                           mode=Timer.MODE_ASYNC)
    #
    #     expected_repr_str = \
    #         f'Timer(' \
    #         f'requests={requests_arg}, ' \
    #         f'seconds={float(seconds_arg)}, ' \
    #         f'mode=Timer.MODE_ASYNC, ' \
    #         f'async_q_size={Timer.DEFAULT_ASYNC_Q_SIZE})'
    #
    #     assert repr(a_throttle) == expected_repr_str
    #
    #     a_throttle.start_shutdown()
    #
    #     #######################################################################
    #     # throttle with async_q_size specified
    #     #######################################################################
    #     q_size = requests_arg * 3
    #     a_throttle = Timer(requests=requests_arg,
    #                           seconds=seconds_arg,
    #                           mode=Timer.MODE_ASYNC,
    #                           async_q_size=q_size)
    #
    #     expected_repr_str = \
    #         f'Timer(' \
    #         f'requests={requests_arg}, ' \
    #         f'seconds={float(seconds_arg)}, ' \
    #         f'mode=Timer.MODE_ASYNC, ' \
    #         f'async_q_size={q_size})'
    #
    #     assert repr(a_throttle) == expected_repr_str
    #
    #     a_throttle.start_shutdown()

