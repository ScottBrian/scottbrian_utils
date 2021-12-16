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


########################################################################
# Cmds test exceptions
########################################################################
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


########################################################################
# timeout_arg fixture
########################################################################
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


########################################################################
# who_arg fixture
########################################################################
who_arg_list = ['beta', 'charlie', 'both']


@pytest.fixture(params=who_arg_list)  # type: ignore
def who_arg(request: Any) -> str:
    """Using different cmd targets.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(str, request.param)


#######################################################################
# cmd_arg fixture
########################################################################
cmd_arg_list = [0, '0', 0.0, 'hello', 1, [1, 2, 3], ('a', 'b', 'c')]


@pytest.fixture(params=cmd_arg_list)  # type: ignore
def cmd_arg(request: Any) -> Any:
    """Using different cmds.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


#######################################################################
# start_arg fixture
########################################################################
start_arg_list = ['before', 'mid1', 'mid2', 'after']


@pytest.fixture(params=start_arg_list)  # type: ignore
def start_arg(request: Any) -> str:
    """Using different remote thread start points.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(str, request.param)


########################################################################
# TestCmdsBasic class to test Cmds methods
########################################################################
class TestCmdsErrors:
    """TestCmdsErrors class."""
    def test_cmds_timeout(self,
                          timeout_arg: float) -> None:
        """test_cmds_timeout.

        Args:
            timeout_arg: number of seconds to use for timeout value
                           on get_cmd request

        """
        def f1() -> None:
            """Beta f1 function."""
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


########################################################################
# TestCmdsExamples class
########################################################################
class TestCmdsExamples:
    """Test examples of Cmds."""

    ####################################################################
    # test_cmds_example1
    ####################################################################
    def test_cmds_example1(self,
                           capsys: Any) -> None:
        """Test cmds example1.

        Args:
            capsys: pytest fixture to capture print output

        """
        def f1() -> None:
            """Beta f1 function."""
            print('f1 entered')
            print(cmds.get_cmd('beta'))
            print('f1 exiting')

        print('mainline entered')
        cmds = Cmds()
        f1_thread = threading.Thread(target=f1)
        f1_thread.start()
        cmds.queue_cmd('beta', 'exit now')
        f1_thread.join()
        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += 'f1 entered\n'
        expected_result += 'exit now\n'
        expected_result += 'f1 exiting\n'
        expected_result += 'mainline exiting\n'
        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_cmds_example2
    ####################################################################
    def test_cmds_example2(self,
                           capsys: Any) -> None:
        """Test cmds example2.

        Args:
            capsys: pytest fixture to capture print output

        """
        def f1() -> None:
            """Beta f1 function."""
            print('f1 entered')
            cmds.start_clock(clock_iter=1)
            cmds.get_cmd('beta')
            assert 2 <= cmds.duration() <= 3
            print('f1 exiting')

        print('mainline entered')
        cmds = Cmds()
        f1_thread = threading.Thread(target=f1)
        f1_thread.start()
        cmds.pause(2.5, clock_iter=1)
        cmds.queue_cmd('beta', 'exit now')
        f1_thread.join()
        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += 'f1 entered\n'
        expected_result += 'f1 exiting\n'
        expected_result += 'mainline exiting\n'
        captured = capsys.readouterr().out

        assert captured == expected_result

########################################################################
# TestCmdsCmds class
########################################################################
class TestCmdsCmds:
    """Test examples of Cmds."""

    ####################################################################
    # test_cmds_example1
    ####################################################################
    def test_cmds_cmds1(self,
                        who_arg: str,
                        cmd_arg: Any,
                        start_arg: str) -> None:
        """Test cmds queue_cmd and get_cmd methods.

        Args:
            who_arg: who to send cmd to
            cmd_arg: what to send

        """

        def f1() -> None:
            """Beta f1 function."""
            logger.debug('f1 beta entered')
            f1_event.set()
            assert cmds.get_cmd('beta') == 'go'
            while True:
                my_cmd = cmds.get_cmd('beta')
                if my_cmd == 'exit now':
                    break
                else:
                    assert my_cmd == cmd_arg
            logger.debug('f1 beta exiting')

        def f2() -> None:
            """Charlie f2 function."""
            logger.debug('f2 charlie entered')
            f2_event.set()
            cmds.queue_cmd('alpha', 'charlie ready')
            assert cmds.get_cmd('charlie') == 'go'
            while True:
                my_cmd = cmds.get_cmd('charlie')
                if my_cmd == 'exit now':
                    break
                else:
                    assert my_cmd == cmd_arg

            logger.debug('f2 charlie exiting')

        logger.debug('mainline entered')
        cmds = Cmds()
        f1_event = threading.Event()
        f2_event = threading.Event()

        if who_arg == 'beta' or who_arg == 'both':
            f1_thread = threading.Thread(target=f1)
            if start_arg == 'before':
                logger.debug('mainline starting beta before')
                f1_thread.start()
                f1_event.wait()
            cmds.queue_cmd('beta')  # no arg, default is 'go'
            if start_arg == 'mid1':
                logger.debug('mainline starting beta mid1')
                f1_thread.start()
                f1_event.wait()
            cmds.queue_cmd('beta', cmd_arg)
            if start_arg == 'mid2':
                logger.debug('mainline starting beta mid2')
                f1_thread.start()
                f1_event.wait()
            if who_arg == 'beta':
                cmds.queue_cmd(who_arg, 'exit now')
            else:
                cmds.queue_cmd('beta', 'exit now')
            if start_arg == 'after':
                logger.debug('mainline starting beta after')
                f1_thread.start()
                f1_event.wait()
            logger.debug('mainline about to join f1 beta')
            f1_thread.join()

        if who_arg == 'charlie' or who_arg == 'both':
            logger.debug('mainline starting charlie')
            f2_thread = threading.Thread(target=f2)
            if start_arg == 'before':
                logger.debug('mainline starting charlie before')
                f2_thread.start()
                f2_event.wait()
            cmds.queue_cmd('charlie')  # no arg, default is 'go'
            if start_arg == 'mid1':
                logger.debug('mainline starting charlie mid1')
                f2_thread.start()
                f2_event.wait()
            cmds.queue_cmd('charlie', cmd_arg)
            if start_arg == 'mid2':
                logger.debug('mainline starting charlie mid2')
                f2_thread.start()
                f2_event.wait()
            if who_arg == 'charlie':
                cmds.queue_cmd(who_arg, 'exit now')
            else:
                cmds.queue_cmd('charlie', 'exit now')
            logger.debug('mainline about to join f2 charlie')
            if start_arg == 'after':
                logger.debug('mainline starting charlie after')
                f2_thread.start()
                f2_event.wait()
            f2_thread.join()

        logger.debug('mainline exiting')



    ####################################################################
    # repr with mode async
    ####################################################################
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

