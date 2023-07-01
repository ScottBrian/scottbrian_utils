"""test_pauser.py module."""

########################################################################
# Standard Library
########################################################################
import itertools
import logging
import re
import sys
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
from scottbrian_utils.pauser import IncorrectInput
from scottbrian_utils.diag_msg import get_formatted_call_sequence as cseq

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


@pytest.fixture(params=interval_arg_list)
def interval_arg(request: Any) -> IntFloat:
    """Using different seconds for interval.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


########################################################################
# min_max_interval_msecs_arg
########################################################################
min_max_interval_msecs_arg_list = [(1, 1),
                                   (1, 2),
                                   (1, 3),
                                   (1, 100),
                                   (101, 200)]


@pytest.fixture(params=min_max_interval_msecs_arg_list)
def min_max_interval_msecs_arg(request: Any) -> tuple[int, int]:
    """Using different interval ranges.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(tuple[int, int], request.param)


#######################################################################
# increment_arg
########################################################################
increment_arg_list = [1, 2, 3, 5]


@pytest.fixture(params=increment_arg_list)
def increment_arg(request: Any) -> int:
    """Using different increments.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


#######################################################################
# part_time_factor_arg
########################################################################
part_time_factor_arg_list = [0.3, 0.4, 0.5]


@pytest.fixture(params=part_time_factor_arg_list)
def part_time_factor_arg(request: Any) -> float:
    """Using different part time ratios.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(float, request.param)


#######################################################################
# sleep_late_ratio_arg
########################################################################
sleep_late_ratio_arg_list = [0.90, 1.0]


@pytest.fixture(params=sleep_late_ratio_arg_list)
def sleep_late_ratio_arg(request: Any) -> float:
    """Using different sleep ratios.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(float, request.param)


#######################################################################
# iterations_arg
########################################################################
iterations_arg_list = [1, 2, 3]


@pytest.fixture(params=iterations_arg_list)
def iterations_arg(request: Any) -> int:
    """Using different calibration iterations.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# TestPauserErrors class
########################################################################
class TestPauserErrors:
    """TestPauserErrors class."""
    ####################################################################
    # test_pauser_bad_min_interval_secs
    ####################################################################
    def test_pauser_bad_min_interval_secs(self) -> None:
        """Test bad pause min_interval_secs raises error."""
        logger.debug('mainline entered')
        with pytest.raises(IncorrectInput):
            Pauser(min_interval_secs=-1)

        with pytest.raises(IncorrectInput):
            Pauser(min_interval_secs=0)

        logger.debug('mainline exiting')

    ####################################################################
    # test_pauser_bad_part_time_factor
    ####################################################################
    def test_pauser_bad_part_time_factor(self) -> None:
        """Test bad part_time_factor raises error."""
        logger.debug('mainline entered')
        with pytest.raises(IncorrectInput):
            Pauser(part_time_factor=-1)

        with pytest.raises(IncorrectInput):
            Pauser(part_time_factor=0)

        with pytest.raises(IncorrectInput):
            Pauser(part_time_factor=1.1)

        logger.debug('mainline exiting')

    ####################################################################
    # test_pause_negative_interval
    ####################################################################
    def test_pause_negative_interval(self) -> None:
        """Test negative pause time raises error."""
        logger.debug('mainline entered')
        with pytest.raises(IncorrectInput):
            Pauser().pause(-1)

        logger.debug('mainline exiting')

    ####################################################################
    # test_calibrate_bad_min_interval_msecs
    ####################################################################
    def test_calibrate_bad_min_interval_msecs(self) -> None:
        """Test zero or negative min_interval_msecs raises error."""
        logger.debug('mainline entered')
        with pytest.raises(IncorrectInput):
            Pauser().calibrate(min_interval_msecs=-1)

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(min_interval_msecs=0)

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(min_interval_msecs=1.1)  # type: ignore

        logger.debug('mainline exiting')

    ####################################################################
    # test_calibrate_bad_max_interval_msecs
    ####################################################################
    def test_calibrate_bad_max_interval_msecs(self) -> None:
        """Test bad max_interval_msecs raises error."""
        logger.debug('mainline entered')
        with pytest.raises(IncorrectInput):
            Pauser().calibrate(max_interval_msecs=-1)

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(max_interval_msecs=0)

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(max_interval_msecs=1.1)  # type: ignore

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(min_interval_msecs=2,
                               max_interval_msecs=1)

        logger.debug('mainline exiting')

    ####################################################################
    # test_calibrate_bad_increment
    ####################################################################
    def test_calibrate_bad_increment(self) -> None:
        """Test zero or negative min_interval_msecs raises error."""
        logger.debug('mainline entered')
        with pytest.raises(IncorrectInput):
            Pauser().calibrate(increment=-1)

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(increment=0)

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(increment=1.1)  # type: ignore

        logger.debug('mainline exiting')

    ####################################################################
    # test_calibrate_bad_part_time_factor
    ####################################################################
    def test_calibrate_bad_part_time_factor(self) -> None:
        """Test bad part_time_factor raises error."""
        logger.debug('mainline entered')
        with pytest.raises(IncorrectInput):
            Pauser().calibrate(part_time_factor=-1)

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(part_time_factor=0)

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(part_time_factor=1.1)

        logger.debug('mainline exiting')

    ####################################################################
    # test_calibrate_bad_max_sleep_late_ratio
    ####################################################################
    def test_calibrate_bad_max_sleep_late_ratio(self) -> None:
        """Test bad part_time_factor raises error."""
        logger.debug('mainline entered')
        with pytest.raises(IncorrectInput):
            Pauser().calibrate(max_sleep_late_ratio=-1)

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(max_sleep_late_ratio=0)

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(max_sleep_late_ratio=1.1)

        logger.debug('mainline exiting')

    ####################################################################
    # test_calibrate_bad_iterations
    ####################################################################
    def test_calibrate_bad_iterations(self) -> None:
        """Test bad part_time_factor raises error."""
        logger.debug('mainline entered')
        with pytest.raises(IncorrectInput):
            Pauser().calibrate(iterations=-1)

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(iterations=0)

        with pytest.raises(IncorrectInput):
            Pauser().calibrate(iterations=1.1)  # type: ignore

        logger.debug('mainline exiting')

    ####################################################################
    # test_get_metrics_bad_min_interval_msecs
    ####################################################################
    def test_get_metrics_bad_min_interval_msecs(self) -> None:
        """Test zero or negative min_interval_msecs raises error."""
        logger.debug('mainline entered')
        with pytest.raises(IncorrectInput):
            Pauser().get_metrics(min_interval_msecs=-1)

        with pytest.raises(IncorrectInput):
            Pauser().get_metrics(min_interval_msecs=0)

        with pytest.raises(IncorrectInput):
            Pauser().get_metrics(min_interval_msecs=1.1)  # type: ignore

        logger.debug('mainline exiting')

    ####################################################################
    # test_get_metrics_bad_max_interval_msecs
    ####################################################################
    def test_get_metrics_bad_max_interval_msecs(self) -> None:
        """Test bad max_interval_msecs raises error."""
        logger.debug('mainline entered')
        with pytest.raises(IncorrectInput):
            Pauser().get_metrics(max_interval_msecs=-1)

        with pytest.raises(IncorrectInput):
            Pauser().get_metrics(max_interval_msecs=0)

        with pytest.raises(IncorrectInput):
            Pauser().get_metrics(max_interval_msecs=1.1)  # type: ignore

        with pytest.raises(IncorrectInput):
            Pauser().get_metrics(min_interval_msecs=2,
                                 max_interval_msecs=1)

        logger.debug('mainline exiting')

    ####################################################################
    # test_get_metrics_bad_iterations
    ####################################################################
    def test_get_metrics_bad_iterations(self) -> None:
        """Test bad part_time_factor raises error."""
        logger.debug('mainline entered')
        with pytest.raises(IncorrectInput):
            Pauser().get_metrics(iterations=-1)

        with pytest.raises(IncorrectInput):
            Pauser().get_metrics(iterations=0)

        with pytest.raises(IncorrectInput):
            Pauser().get_metrics(iterations=1.1)  # type: ignore

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

    ####################################################################
    # test_pauser_example2
    ####################################################################
    def test_pauser_example2(self,
                             capsys: Any) -> None:
        """Test pauser example2.

        Args:
            capsys: pytest fixture to capture print output

        """
        print('mainline entered')

        from scottbrian_utils.pauser import Pauser
        pauser = Pauser()
        print(pauser)
        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += ('Pauser(min_interval_secs=0.03, '
                            'part_time_factor=0.4)\n')
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_pauser_example3
    ####################################################################
    def test_pauser_example3(self,
                             capsys: Any) -> None:
        """Test pauser example3.

        Args:
            capsys: pytest fixture to capture print output

        """
        print('mainline entered')

        from scottbrian_utils.pauser import Pauser
        pauser = Pauser(min_interval_secs=0.02,
                        part_time_factor=0.3)
        print(repr(pauser))
        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += ('Pauser(min_interval_secs=0.02, '
                            'part_time_factor=0.3)\n')
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_pauser_example4
    ####################################################################
    def test_pauser_example4(self,
                             capsys: Any) -> None:
        """Test pauser example4.

        Args:
            capsys: pytest fixture to capture print output

        """
        print('mainline entered')

        from scottbrian_utils.pauser import Pauser
        pauser = Pauser(min_interval_secs=1.0)
        pauser.calibrate(min_interval_msecs=5,
                         max_interval_msecs=100,
                         increment=5)
        print(f'{pauser.min_interval_secs=}')

        print('mainline exiting')

        expected_result = 'mainline entered\n'
        if sys.version_info.minor >= 11:
            expected_result += 'pauser.min_interval_secs=0.005\n'
        else:
            expected_result += 'pauser.min_interval_secs=0.015\n'
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        match_str = 'pauser.min_interval_secs=0.0[0-9]{1,2}'

        found_item = re.match(match_str, captured)
        if found_item:
            expected_result = re.sub(match_str,
                                     found_item.group(),
                                     expected_result)

        assert captured == expected_result

    ####################################################################
    # test_pauser_example5
    ####################################################################
    def test_pauser_example5(self,
                             capsys: Any) -> None:
        """Test pauser example5.

        Args:
            capsys: pytest fixture to capture print output

        """
        print('mainline entered')

        from scottbrian_utils.pauser import Pauser
        pauser = Pauser()
        metrics = pauser.get_metrics(min_interval_msecs=100,
                                     max_interval_msecs=100,
                                     iterations=3)
        print(f'{metrics.pause_ratio=:.1f}, '
              f'{metrics.sleep_ratio=:.1f}')

        print('mainline exiting')

        expected_result = 'mainline entered\n'
        if sys.version_info.minor >= 11:
            expected_result += ('metrics.pause_ratio=1.0, '
                                'metrics.sleep_ratio=0.8\n')
        else:
            expected_result += ('metrics.pause_ratio=1.0, '
                                'metrics.sleep_ratio=0.6\n')
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_pauser_example6
    ####################################################################
    def test_pauser_example6(self,
                             capsys: Any) -> None:
        """Test pauser example6.

        Args:
            capsys: pytest fixture to capture print output

        """
        print('mainline entered')

        from scottbrian_utils.pauser import Pauser
        pauser = Pauser(min_interval_secs=1.0)
        metrics = pauser.get_metrics(min_interval_msecs=980,
                                     max_interval_msecs=1000,
                                     iterations=3)
        print(f'{metrics.pause_ratio=:.1f}, '
              f'{metrics.sleep_ratio=:.1f}')

        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += ('metrics.pause_ratio=1.0, '
                            'metrics.sleep_ratio=0.0\n')
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_pauser_example7
    ####################################################################
    def test_pauser_example7(self,
                             capsys: Any) -> None:
        """Test pauser example7.

        Args:
            capsys: pytest fixture to capture print output

        """
        print('mainline entered')

        from scottbrian_utils.pauser import Pauser
        pauser = Pauser()
        pauser.pause(1)

        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_pauser_example8
    ####################################################################
    def test_pauser_example8(self,
                             capsys: Any) -> None:
        """Test pauser example8.

        Args:
            capsys: pytest fixture to capture print output

        """
        print('mainline entered')

        from scottbrian_utils.pauser import Pauser
        import time
        pauser = Pauser()
        start_time = time.perf_counter_ns()
        pauser.pause(0.5)
        stop_time = time.perf_counter_ns()
        interval = (stop_time - start_time) * Pauser.NS_2_SECS
        print(f'paused for {interval:.1f} seconds')

        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += 'paused for 0.5 seconds\n'
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_pauser_example9
    ####################################################################
    def test_pauser_example9(self,
                             capsys: Any) -> None:
        """Test pauser example9.

        Args:
            capsys: pytest fixture to capture print output

        """
        print('mainline entered')

        from scottbrian_utils.pauser import Pauser
        import time
        pauser = Pauser()
        start_time = time.perf_counter_ns()
        pauser.pause(0.25)
        stop_time = time.perf_counter_ns()
        interval = (stop_time - start_time) * Pauser.NS_2_SECS
        print(f'paused for {interval:.2f} seconds')

        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += 'paused for 0.25 seconds\n'
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
        """Test pauser pause method.

        Args:
            interval_arg: number of seconds to pause

        """
        logger.debug('mainline entered')
        pauser = Pauser()

        logger.debug(f'{pauser.min_interval_secs=}')
        logger.debug(f'{pauser.part_time_factor=}')

        pauser.total_sleep_time = 0.0

        start_time = time.perf_counter_ns()
        pauser.pause(interval_arg)
        stop_time = time.perf_counter_ns()

        actual_interval = (stop_time - start_time) * Pauser.NS_2_SECS
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

        if 0 < interval_arg:
            assert 99.0 <= actual_interval_pct <= 101.0

        logger.debug('mainline exiting')


########################################################################
# TestPauserPause class
########################################################################
class TestPauserCalibrate:
    """Test pause calibration."""

    ####################################################################
    # test_pauser_calibration_defaults
    ####################################################################
    def test_pauser_calibration_defaults(self) -> None:
        """Test pauser calibration method with defaults."""
        logger.debug('mainline entered')
        pauser = Pauser()
        pauser.calibrate()

        logger.debug(f'calibration results: '
                     f'{pauser.min_interval_secs=}, '
                     f'{pauser.part_time_factor=} ')

        metric_results = pauser.get_metrics()
        logger.debug(f'metrics results: '
                     f'{metric_results.pause_ratio=:.4f}, '
                     f'{metric_results.sleep_ratio=:.4f}')

        logger.debug('mainline exiting')

    ####################################################################
    # test_pauser_calibration
    ####################################################################
    def test_pauser_calibration(self,
                                monkeypatch: Any,
                                sleep_late_ratio_arg: float
                                ) -> None:
        """Test pauser calibration method.

        Args:
            monkeypatch: pytest fixture for monkey-patching
            sleep_late_ratio_arg: threshold of lateness

        """
        logger.debug('mainline entered')
        low_interval_ratio = sleep_late_ratio_arg - .01
        high_interval_ratio = sleep_late_ratio_arg + .01
        min_interval = 1
        for max_interval in range(1, 4):
            for num_iterations in range(1, 4):

                num_intervals = max_interval - min_interval + 1
                num_combos = num_intervals * num_iterations
                print(f'\n{num_combos=}')
                combos = itertools.product(
                    itertools.product((0.0, 4.2),
                                      repeat=num_iterations),
                    repeat=num_intervals)

                for rt_vals in combos:
                    print(f'\n{rt_vals=}')
                    print(f'\n{max_interval=}, '
                          f'{num_iterations=}')

                    expected_min_interval_secs = 0.001
                    found_min = False
                    for rev_interval_idx in range(
                            len(rt_vals)-1, -1, -1):
                        for rev_iter_idx in range(num_iterations-1, -1, -1):
                            print(f'{rev_interval_idx=}, '
                                  f'{rev_iter_idx=}, '
                                  f'{rt_vals[rev_interval_idx][rev_iter_idx]}')
                            if rt_vals[rev_interval_idx][rev_iter_idx] >= 4.2:
                                expected_min_interval_secs = (
                                        (rev_interval_idx + 1) * 0.001)
                                found_min = True
                                break
                        if found_min:
                            break

                    call_num: int = -2

                    def mock_time() -> float:
                        nonlocal call_num
                        call_num += 1
                        if call_num % 2 != 0:  # if odd
                            iter_num: int = 0
                            iter_idx: int = 0
                            interval_idx: int = 0
                            ret_time_value = 0.0
                        else:  # even
                            iter_num = call_num // 2
                            iter_idx = iter_num % num_iterations
                            interval_idx = iter_num // num_iterations
                            interval_value = (interval_idx + 1) * .001
                            ret_time_value = rt_vals[interval_idx][iter_idx]
                            if ret_time_value == 4.2:
                                ret_time_value = ((interval_value
                                                  * high_interval_ratio)
                                                  * Pauser.SECS_2_NS)
                                call_num += (num_iterations - (iter_idx+1)) * 2
                            else:
                                ret_time_value = ((interval_value
                                                  * low_interval_ratio)
                                                  * Pauser.SECS_2_NS)
                        print(f'{call_num=}, '
                              f'{iter_num=}, '
                              f'{iter_idx=}, '
                              f'{interval_idx=}, '
                              f'{ret_time_value=}, '
                              f'{cseq()=}')
                        return ret_time_value

                    monkeypatch.setattr(time, 'perf_counter_ns', mock_time)

                    pauser = Pauser()
                    pauser.calibrate(
                        min_interval_msecs=min_interval,
                        max_interval_msecs=max_interval,
                        increment=1,
                        part_time_factor=0.4,  # part_time_factor_arg,
                        max_sleep_late_ratio=sleep_late_ratio_arg,
                        iterations=num_iterations)

                    print(f'calibration results: '
                          f'{expected_min_interval_secs=}, '
                          f'{pauser.min_interval_secs=}, '
                          f'{pauser.part_time_factor=} ')

                    assert (expected_min_interval_secs
                            == pauser.min_interval_secs)

    ####################################################################
    # test_pauser_calibration2
    ####################################################################
    def test_pauser_calibration2(self,
                                 min_max_interval_msecs_arg: tuple[int, int],
                                 part_time_factor_arg: float,
                                 increment_arg: int,
                                 sleep_late_ratio_arg: float,
                                 iterations_arg: int) -> None:
        """Test pauser calibration method.

        Args:
            min_max_interval_msecs_arg: range to span
            increment_arg: increment to use for span
            part_time_factor_arg: factor to be applied to sleep time
            sleep_late_ratio_arg: threshold of lateness
            iterations_arg: number of iteration per interval

        """
        logger.debug('mainline entered')
        pauser = Pauser()
        pauser.calibrate(
            min_interval_msecs=min_max_interval_msecs_arg[0],
            max_interval_msecs=min_max_interval_msecs_arg[1],
            increment=increment_arg,
            part_time_factor=part_time_factor_arg,
            max_sleep_late_ratio=sleep_late_ratio_arg,
            iterations=iterations_arg)

        logger.debug(f'calibration results: '
                     f'{pauser.min_interval_secs=}, '
                     f'{pauser.part_time_factor=} ')

        # low_metric_results = pauser.get_metrics(
        #     min_interval_msecs=1,
        #     max_interval_msecs=300,
        #     iterations=3)
        # logger.debug(f'low metrics results: '
        #              f'{low_metric_results.pause_ratio=:.4f}, '
        #              f'{low_metric_results.sleep_ratio=:.4f}')
        #
        # high_metric_results = pauser.get_metrics(
        #     min_interval_msecs=301,
        #     max_interval_msecs=600,
        #     iterations=3)
        #
        # logger.debug(f'high metrics results: '
        #              f'{high_metric_results.pause_ratio=:.4f}, '
        #              f'{high_metric_results.sleep_ratio=:.4f}')

        logger.debug('mainline exiting')

    ####################################################################
    # test_pauser_calibration3
    ####################################################################
    def test_pauser_calibration3(self) -> None:
        """Test pauser calibration method."""
        logger.debug('mainline entered')
        pauser = Pauser()
        pauser.calibrate(
            min_interval_msecs=5,
            max_interval_msecs=100,
            increment=5)

        logger.debug(f'calibration results: '
                     f'{pauser.min_interval_secs=}, '
                     f'{pauser.part_time_factor=} ')

        logger.debug('mainline exiting')


########################################################################
# TestPauserPause class
########################################################################
class TestPauserGetMetrics:
    """Test pause calibration."""

    ####################################################################
    # test_pauser_get_metrics_defaults
    ####################################################################
    def test_pauser_get_metrics_defaults(self) -> None:
        """Test pauser calibration method with defaults."""
        logger.debug('mainline entered')
        pauser = Pauser()

        logger.debug(f'calibration results: '
                     f'{pauser.min_interval_secs=}, '
                     f'{pauser.part_time_factor=} ')

        metric_results = pauser.get_metrics()
        logger.debug(f'metrics results: '
                     f'{metric_results.pause_ratio=:.4f}, '
                     f'{metric_results.sleep_ratio=:.4f}')

        logger.debug('mainline exiting')

    ####################################################################
    # test_pauser_get_metrics_diff_inputs
    ####################################################################
    def test_pauser_get_metrics_diff_inputs(
            self,
            min_max_interval_msecs_arg: tuple[int, int],
            iterations_arg: int) -> None:
        """Test pauser calibration method.

        Args:
            min_max_interval_msecs_arg: range to span
            iterations_arg: number of iteration per interval
        """
        logger.debug('mainline entered')
        pauser = Pauser()

        logger.debug(f'pauser settings: '
                     f'{pauser.min_interval_secs=}, '
                     f'{pauser.part_time_factor=} ')

        metric_results = pauser.get_metrics(
            min_interval_msecs=min_max_interval_msecs_arg[0],
            max_interval_msecs=min_max_interval_msecs_arg[1],
            iterations=iterations_arg)

        logger.debug(f'metrics results: '
                     f'{metric_results.pause_ratio=:.4f}, '
                     f'{metric_results.sleep_ratio=:.4f}')

        logger.debug('mainline exiting')

    ####################################################################
    # test_pauser_get_metrics
    ####################################################################
    def test_pauser_get_metrics(self) -> None:
        """Test pauser calibration method."""
        logger.debug('mainline entered')
        pauser = Pauser(min_interval_secs=0.25,
                        part_time_factor=0.3)

        pause_ratios = []
        sleep_ratios = []
        for min_interval_seconds in [0.001, 0.250]:  # extremes
            pauser.min_interval_secs = min_interval_seconds

            logger.debug(f'metrics pauser settings: '
                         f'{pauser.min_interval_secs=}, '
                         f'{pauser.part_time_factor=} ')

            metric_results = pauser.get_metrics(
                min_interval_msecs=1,
                max_interval_msecs=250,
                iterations=1)

            pause_ratios.append(metric_results.pause_ratio)
            sleep_ratios.append(metric_results.sleep_ratio)
            logger.debug(f'metrics results: '
                         f'{metric_results.pause_ratio=:.4f}, '
                         f'{metric_results.sleep_ratio=:.4f}')

        assert 1.0 < pause_ratios[1]

        assert pause_ratios[1] < pause_ratios[0]

        assert sleep_ratios[1] == 0.0

        assert sleep_ratios[1] < sleep_ratios[0]

        logger.debug('mainline exiting')
