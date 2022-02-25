"""test_pauser.py module."""

########################################################################
# Standard Library
########################################################################
import logging
import re
import threading
import time
from typing import Any, cast, Optional, Union

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.pauser import Pauser
from scottbrian_utils.pauser import NegativePauseTime

########################################################################
# type aliases
########################################################################
IntFloat = Union[int, float]
OptIntFloat = Optional[IntFloat]

########################################################################
# Set up logging
########################################################################
logger = logging.getLogger('test_pauser')
logger.debug('about to start the tests')


########################################################################
# Pauser test exceptions
########################################################################
class ErrorTstPauser(Exception):
    """Base class for exception in this module."""
    pass


########################################################################
# interval_arg fixture
########################################################################
interval_arg_list = [0.0, 0.001, 0.010, 0.100, 0.500, 0.900, 1, 2, 5]


@pytest.fixture(params=interval_arg_list)  # type: ignore
def interval_arg(request: Any) -> IntFloat:
    """Using different seconds for interval.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


########################################################################
# who_arg fixture
########################################################################
who_arg_list = ['beta', 'charlie', 'both']


@pytest.fixture(params=who_arg_list)  # type: ignore
def who_arg(request: Any) -> str:
    """Using different msg targets.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(str, request.param)


#######################################################################
# msg_arg fixture
########################################################################
msg_arg_list = [0, '0', 0.0, 'hello', 1, [1, 2, 3], ('a', 'b', 'c')]


@pytest.fixture(params=msg_arg_list)  # type: ignore
def msg_arg(request: Any) -> Any:
    """Using different msgs.

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
# TestPauserErrors class
########################################################################
class TestPauserErrors:
    """TestPauserErrors class."""
    ####################################################################
    # test_pauser_negative_pause
    ####################################################################
    def test_pauser_negative_pause(self) -> None:
        """Test negative pause time raises error."""
        logger.debug('mainline entered')
        with pytest.raises(NegativePauseTime):
            Pauser().pause(-1)

        logger.debug('mainline exiting')


########################################################################
# TestPauserExamples class
########################################################################
class TestPauserExamples:
    """Test examples of Pauser."""

    ####################################################################
    # test_pauser_example1
    ####################################################################
    def test_pauser_example1(self,
                             capsys: Any) -> None:
        """Test pauser example1.

        Args:
            capsys: pytest fixture to capture print output

        """
        print('mainline entered')

        from scottbrian_utils.pauser import Pauser
        import time
        pauser = Pauser()
        start_time = time.time()
        pauser.pause(1.5)
        print(f'paused for {time.time() - start_time:.1f} seconds')
        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += 'paused for 1.5 seconds\n'
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result


########################################################################
# TestPauserPause class
########################################################################
class TestPauserPause:
    """Test pause method."""

    ####################################################################
    # test_pauser_pause
    ####################################################################
    def test_pauser_pause(self,
                          interval_arg: IntFloat) -> None:
        """Test msgs queue_msg and get_msg methods.

        Args:
            interval_arg: number of seconds to pause

        """
        logger.debug('mainline entered')
        pauser = Pauser()
        start_time = time.time()
        pauser.pause(interval_arg)
        stop_time = time.time()
        actual_interval = stop_time - start_time
        sleep_time = pauser.total_sleep_time
        if 0 < interval_arg:
            actual_interval_pct = (actual_interval/interval_arg) * 100
            sleep_pct = (sleep_time/interval_arg) * 100
        else:
            sleep_pct = 0.0
            actual_interval_pct = 0.0


        logger.debug(f'{interval_arg=}, '
                     f'{actual_interval=:.4f}, '
                     f'{actual_interval_pct=:.4f}%')
        logger.debug(f'{sleep_time=:.4f}, {sleep_pct=:.2f}%')

        assert actual_interval_pct <= 102.0

        logger.debug('mainline exiting')
