"""test_throttle.py module."""

import pytest
import time
import math
from time import time
from datetime import datetime, timedelta
from typing import Any, Callable, cast, Final, Optional, Tuple, Union
from collections import deque
import threading

from scottbrian_utils.flower_box import print_flower_box_msg as flowers

from scottbrian_utils.throttle import Throttle, throttle
from scottbrian_utils.throttle import IncorrectRequestsSpecified
from scottbrian_utils.throttle import IncorrectSecondsSpecified
from scottbrian_utils.throttle import IncorrectModeSpecified
from scottbrian_utils.throttle import IncorrectLbThresholdSpecified
from scottbrian_utils.throttle import IncorrectEarlyCountSpecified
from scottbrian_utils.throttle import IncorrectShutdownCheckSpecified
from scottbrian_utils.throttle import MissingLbThresholdSpecification
from scottbrian_utils.throttle import MissingEarlyCountSpecification
from scottbrian_utils.throttle import EarlyCountNotAllowed
from scottbrian_utils.throttle import LbThresholdNotAllowed
from scottbrian_utils.throttle import ShutdownCheckNotAllowed


###############################################################################
# Throttle test exceptions
###############################################################################
class ErrorTstThrottle(Exception):
    """Base class for exception in this module."""
    pass


class InvalidRouteNum(ErrorTstThrottle):
    """InvalidRouteNum exception class."""
    pass


class InvalidModeNum(ErrorTstThrottle):
    """InvalidModeNum exception class."""
    pass
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
mode_arg_list = [Throttle.MODE_ASYNC,
                 Throttle.MODE_SYNC_LB,
                 Throttle.MODE_SYNC_EC]


@pytest.fixture(params=mode_arg_list)  # type: ignore
def mode_arg(request: Any) -> int:
    """Using different modes.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)

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
# early_count_arg fixture
###############################################################################
tc_shutdown_flag: bool = False


def tc_shutdown_check() -> bool:
    return tc_shutdown_flag


shutdown_check_arg_list = [None, tc_shutdown_check]


@pytest.fixture(params=shutdown_check_arg_list)  # type: ignore
def shutdown_check_arg(request: Any) -> Union[None, Callable[[], bool]]:
    """Using different shutdown_check values.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(Union[None, Callable[[], bool]], request.param)


###############################################################################
# style fixture for @throttle tests
###############################################################################
style_num_list = [1, 2, 3]


@pytest.fixture(params=style_num_list)  # type: ignore
def style_num(request: Any) -> int:
    """Using different throttle styles.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# enabled arg fixture for @throttle tests
###############################################################################
enabled_arg_list = [None,
                    'static_true',
                    'static_false',
                    'dynamic_true',
                    'dynamic_false'
                    ]
# enabled_arg_list = [None]


@pytest.fixture(params=enabled_arg_list)  # type: ignore
def enabled_arg(request: Any) -> Union[None, str]:
    """Determines how to specify throttle_enabled.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(Union[None, str], request.param)


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
# Request class use to verify tests
###############################################################################
class Request:
    """Request class to test throttle."""
    def __init__(self,
                 requests: int,
                 seconds: Union[int, float],
                 throttle_TF: bool = True) -> None:
        """Initialize the request class instance.

        Args:
            requests: number of requests allowed per interval
            seconds: interval for number of allowed requests

        """
        self.requests = requests
        self.seconds = timedelta(seconds=seconds)
        self.request_times = deque()
        self.last_len = 0
        self.throttle_TF = throttle_TF

    def make_request(self) -> None:
        """Make a request."""
        #######################################################################
        # trim queue
        #######################################################################
        self.request_times.append(datetime.utcnow())
        trim_time = self.request_times[-1] - self.seconds
        # print('\nrequests before trim:\n', self.request_times)
        while 0 < len(self.request_times):
            if self.request_times[0] < trim_time:
                self.request_times.popleft()
            else:
                break
        # print('\nrequests after trim:\n', self.request_times)
        if self.throttle_TF:
            assert len(self.request_times) <= self.requests
        else:
            assert len(self.request_times) > self.last_len
        self.last_len = len(self.request_times)


###############################################################################
# TestThrottleBasic class to test Throttle methods
###############################################################################
class TestThrottleErrors:
    """TestThrottle class."""
    def test_throttle_bad_args(self) -> None:
        """test_throttle using bad arguments."""
        #######################################################################
        # bad requests
        #######################################################################
        with pytest.raises(IncorrectRequestsSpecified):
            _ = Throttle(requests=0,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC)
        with pytest.raises(IncorrectRequestsSpecified):
            _ = Throttle(requests=-1,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC)
        with pytest.raises(IncorrectRequestsSpecified):
            _ = Throttle(requests='1',  # type: ignore
                         seconds=1,
                         mode=Throttle.MODE_ASYNC)

        #######################################################################
        # bad seconds
        #######################################################################
        with pytest.raises(IncorrectSecondsSpecified):
            _ = Throttle(requests=1,
                         seconds=0,
                         mode=Throttle.MODE_ASYNC)
        with pytest.raises(IncorrectSecondsSpecified):
            _ = Throttle(requests=1,
                         seconds=-1,
                         mode=Throttle.MODE_ASYNC)
        with pytest.raises(IncorrectSecondsSpecified):
            _ = Throttle(requests=1,
                         seconds='1',  # type: ignore
                         mode=Throttle.MODE_ASYNC)

        #######################################################################
        # bad mode
        #######################################################################
        with pytest.raises(IncorrectModeSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=-1)
        with pytest.raises(IncorrectModeSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=0)
        with pytest.raises(IncorrectModeSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_MAX+1)
        with pytest.raises(IncorrectModeSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode='1')  # type: ignore

        #######################################################################
        # bad early_count
        #######################################################################
        with pytest.raises(EarlyCountNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC,
                         early_count=0)
        with pytest.raises(EarlyCountNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC,
                         early_count=1)
        with pytest.raises(MissingEarlyCountSpecification):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_EC)
        with pytest.raises(EarlyCountNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_LB,
                         early_count=1)
        with pytest.raises(IncorrectEarlyCountSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_EC,
                         early_count=-1)
        with pytest.raises(IncorrectEarlyCountSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_EC,
                         early_count='1')  # type: ignore
        #######################################################################
        # bad lb_threshold
        #######################################################################
        with pytest.raises(LbThresholdNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC,
                         lb_threshold=1)
        with pytest.raises(LbThresholdNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC,
                         lb_threshold=0)
        with pytest.raises(LbThresholdNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_EC,
                         lb_threshold=0)
        with pytest.raises(MissingLbThresholdSpecification):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_LB)
        with pytest.raises(IncorrectLbThresholdSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_LB,
                         lb_threshold=-1)
        with pytest.raises(IncorrectLbThresholdSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_LB,
                         lb_threshold='1')  # type: ignore

        #######################################################################
        # bad shut_down  (no missing check since shutdown_check is optional)
        #######################################################################
        with pytest.raises(IncorrectShutdownCheckSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC,
                         shutdown_check=1)  # type: ignore
        with pytest.raises(IncorrectShutdownCheckSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC,
                         shutdown_check='1')  # type: ignore
        with pytest.raises(ShutdownCheckNotAllowed):
            def sd_check() -> bool:
                return True
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.SYNC,
                         shutdown_check=sd_check)
        with pytest.raises(ShutdownCheckNotAllowed):
            def sd_check() -> bool:
                return True
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.SYNC_EC,
                         shutdown_check=sd_check)
        with pytest.raises(ShutdownCheckNotAllowed):
            def sd_check() -> bool:
                return True
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.SYNC_LB,
                         shutdown_check=sd_check)
###############################################################################
# TestThrottleBasic class to test Throttle methods
###############################################################################
class TestThrottleBasic:

    ###########################################################################
    # len checks
    ###########################################################################
    def test_throttle_len(self,
                          requests_arg: int) -> None:
        """Test the len of throttle.

        Args:
            requests_arg: fixture that provides args

        """
        # create a throttle with a long enough interval to ensure that we
        # can populate the request_q and get the length before we start
        # dequeing requests from it
        a_throttle = Throttle(requests=requests_arg,
                              seconds=60,
                              mode=Throttle.MODE_ASYNC)

        def dummy_func(throttle_obj, num_requests, an_event) -> None:
            assert len(throttle_obj) == num_requests  # -1
            an_event.set()
        event = threading.Event()
        for i in range(requests_arg):
            a_throttle.send_async(dummy_func, args=(a_throttle,
                                               requests_arg,
                                               event))

        # time.sleep(2)  # wait 2 seconds to give scheduler time to react
        #
        # # assert is for 1 less than queued because the first request
        # # will be scheduled almost immediately
        # assert len(a_throttle) == requests_arg-1
        event.wait()
        # start_shutdown will return when the request_q cleanup is complete
        a_throttle.start_shutdown()

    ###########################################################################
    # repr with mode async
    ###########################################################################
    def test_throttle_repr_async(self,
                                 requests_arg: int,
                                 seconds_arg: Union[int, float],
                                 shutdown_check_arg: Union[None,
                                                           Callable[[], bool]]
                                 ) -> None:
        """test_throttle repr mode 1 with various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args
            shutdown_check_arg: fixture that provides args

        """
        a_throttle = Throttle(requests=requests_arg,
                              seconds=seconds_arg,
                              mode=Throttle.MODE_ASYNC,
                              shutdown_check=shutdown_check_arg)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={float(seconds_arg)}, ' \
            f'mode=Throttle.MODE_ASYNC'

        if shutdown_check_arg:
            expected_repr_str += f', shutdown_check=' \
                                 f'{shutdown_check_arg.__name__}'
        expected_repr_str += ')'
        assert repr(a_throttle) == expected_repr_str

    ###########################################################################
    # repr with mode sync
    ###########################################################################
    def test_throttle_repr_sync(self,
                                requests_arg: int,
                                seconds_arg: Union[int, float],
                                ) -> None:
        """test_throttle repr mode 2 with various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args
        """
        a_throttle = Throttle(requests=requests_arg,
                              seconds=seconds_arg,
                              mode=Throttle.MODE_SYNC)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={float(seconds_arg)}, ' \
            f'mode=Throttle.MODE_SYNC)

        assert repr(a_throttle) == expected_repr_str
    ###########################################################################
    # repr with mode sync early count
    ###########################################################################
    def test_throttle_repr_sync_ec(self,
                                   requests_arg: int,
                                   seconds_arg: Union[int, float],
                                   early_count_arg: int,
                                   ) -> None:
        """test_throttle repr mode 2 with various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args
            early_count_arg: fixture that provides args
        """
        a_throttle = Throttle(requests=requests_arg,
                              seconds=seconds_arg,
                              mode=Throttle.MODE_SYNC_EC,
                              early_count=early_count_arg)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={float(seconds_arg)}, ' \
            f'mode=Throttle.MODE_SYNC_EC), ' \
            f'early_count={early_count_arg})'

        assert repr(a_throttle) == expected_repr_str

    ###########################################################################
    # repr with mode sync leaky bucket
    ###########################################################################
    def test_throttle_repr_sync_lb(self,
                                   requests_arg: int,
                                   seconds_arg: Union[int, float],
                                   lb_threshold_arg: Union[int, float],
                                   ) -> None:
        """test_throttle repr with various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args
            lb_threshold_arg: fixture that provides args
        """
        a_throttle = Throttle(requests=requests_arg,
                              seconds=seconds_arg,
                              mode=Throttle.MODE_SYNC_LB,
                              lb_threshold=lb_threshold_arg)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={float(seconds_arg)}, ' \
            f'mode=Throttle.MODE_SYNC_LB), ' \
            f'lb_threshold={float(lb_threshold_arg)})'

        assert repr(a_throttle) == expected_repr_str


###############################################################################
# TestThrottleDecoratorErrors class
###############################################################################
class TestThrottleDecoratorErrors:
    """TestThrottleDecoratorErrors class."""
    def test_pie_throttle_bad_args(self) -> None:
        """test_throttle using bad arguments."""
        #######################################################################
        # bad requests
        #######################################################################
        with pytest.raises(IncorrectRequestsSpecified):
            @throttle(requests=0, seconds=1, mode=Throttle.MODE_ASYNC)
            def f1():
                print('42')
            f1()

        with pytest.raises(IncorrectRequestsSpecified):
            @throttle(requests=-1, seconds=1, mode=Throttle.MODE_ASYNC)
            def f1():
                print('42')
            f1()

        with pytest.raises(IncorrectRequestsSpecified):
            @throttle(requests='1', seconds=1,
                      mode=Throttle.MODE_ASYNC)  # type: ignore
            def f1():
                print('42')
            f1()
        #######################################################################
        # bad seconds
        #######################################################################
        with pytest.raises(IncorrectSecondsSpecified):
            @throttle(requests=1, seconds=0, mode=Throttle.MODE_ASYNC)
            def f1():
                print('42')
            f1()

        with pytest.raises(IncorrectSecondsSpecified):
            @throttle(requests=1, seconds=-1, mode=Throttle.MODE_ASYNC)
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectSecondsSpecified):
            @throttle(requests=1, seconds='1',
                      mode=Throttle.MODE_ASYNC)  # type: ignore
            def f1():
                print('42')
            f1()

        #######################################################################
        # bad mode
        #######################################################################
        with pytest.raises(IncorrectModeSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=-1)
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectModeSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=0)
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectModeSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_MAX+1)
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectModeSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode='1')  # type: ignore
            def f1():
                print('42')
            f1()

        #######################################################################
        # bad early_count
        #######################################################################
        with pytest.raises(EarlyCountNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_ASYNC,
                      early_count=1)
            def f1():
                print('42')
            f1()
        with pytest.raises(EarlyCountNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC,
                      early_count=1)
            def f1():
                print('42')
            f1()
        with pytest.raises(MissingEarlyCountSpecification):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_EC)
            def f1():
                print('42')
            f1()
        with pytest.raises(EarlyCountNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_LB,
                      early_count=1)
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectEarlyCountSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_EC,
                      early_count=-1)
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectEarlyCountSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_EC,
                      early_count='1')  # type: ignore
            def f1():
                print('42')
            f1()
        #######################################################################
        # bad lb_threshold
        #######################################################################
        with pytest.raises(LbThresholdNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_ASYNC,
                      lb_threshold=1)
            def f1():
                print('42')
            f1()
        with pytest.raises(LbThresholdNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC,
                      lb_threshold=1)
            def f1():
                print('42')
            f1()
        with pytest.raises(LbThresholdNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_EC,
                      lb_threshold=0)
            def f1():
                print('42')
            f1()
        with pytest.raises(MissingLbThresholdSpecification):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_LB)
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectLbThresholdSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_LB,
                      lb_threshold=-1)
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectLbThresholdSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_LB,
                      lb_threshold='1')  # type: ignore
            def f1():
                print('42')
            f1()

        #######################################################################
        # bad shut_down (no missing check since shutdown_check is optional)
        #######################################################################
        with pytest.raises(IncorrectShutdownCheckSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_ASYNC,
                      shutdown_check=1)  # type: ignore
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectShutdownCheckSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_ASYNC,
                      shutdown_check='1')  # type: ignore
            def f1():
                print('42')
            f1()
        with pytest.raises(ShutdownCheckNotAllowed):
            def sd_check() -> bool:
                return True
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC,
                      shutdown_check=sd_check)  # type: ignore
            def f1():
                print('42')
            f1()
        with pytest.raises(ShutdownCheckNotAllowed):
            def sd_check() -> bool:
                return True
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_EC,
                      shutdown_check=sd_check)  # type: ignore
            def f1():
                print('42')
            f1()
        with pytest.raises(ShutdownCheckNotAllowed):
            def sd_check() -> bool:
                return True
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_LB,
                      shutdown_check=sd_check)  # type: ignore
            def f1():
                print('42')
            f1()

###############################################################################
# TestThrottleDecoratorBasic class
###############################################################################
class TestThrottleDecoratorBasic:
    """TestThrottleDecoratorBasic class."""
    def test_pie_throttle(self,
                          requests_arg: int,
                          seconds_arg: Union[int, float]
                          ) -> None:
        """test_throttle using int for seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args
        """
        a_requests = requests_arg
        a_seconds = timedelta(seconds=seconds_arg)
        a_request_times = deque()

        @throttle(requests=requests_arg,
                  seconds=seconds_arg)
        def make_request() -> None:
            """Make a request."""
            #######################################################################
            # trim queue
            #######################################################################
            a_request_times.append(datetime.utcnow())
            trim_time = a_request_times[-1] - a_seconds
            # print('\nrequests before trim:\n', a_request_times)
            while 0 < len(a_request_times):
                if a_request_times[0] < trim_time:
                    a_request_times.popleft()
                else:
                    break
            # print('\nrequests after trim:\n', a_request_times)
            assert len(a_request_times) <= a_requests

        for i in range(requests_arg*3):
            make_request()


###############################################################################
# TestThrottle class
###############################################################################
class TestThrottle:
    """Class TestThrottle.

    The following section tests each combination of arguments to the throttle.
    
    For the decorator, there are three styles of decoration (using pie, 
    calling with the function as the first parameter, and calling the 
    decorator with the function specified after the call. This test is 
    especially useful to ensure that the type hints are working correctly, 
    and that all combinations are accepted by python.
    
    The non-decorator cases will be simpler, with the exception of 
    doing some explicit calls to shutdown the throttle (which is not possible 
    with the decorator style - for this, we can only set a bit that is 
    checked by the shutdown_check function passed into the throttle). 

    The following keywords with various values and in all combinations are
    tested:
        requests - various increments 
        seconds - various increments, both int and float
        throttle_enabled - true/false

    """
    ###########################################################################
    # test_throttle_async
    ###########################################################################
    def test_throttle_async(self,
                            requests_arg: int,
                            seconds_arg: Union[int, float],
                            shutdown_check_arg: Union[None,
                                                      Callable[[], bool]],
                            send_interval_mult_arg: float
                            ) -> None:
        """Method to start throttle mode1 tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            shutdown_check_arg: function to call to check for shutdown
            send_interval_mult_arg: interval between each send of a request
        """
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        self.throttle_router(requests=requests_arg,
                             seconds=seconds_arg,
                             mode=Throttle.MODE_ASYNC,
                             early_count=0,
                             lb_threshold=0,
                             shutdown_check=shutdown_check_arg,
                             send_interval=send_interval)

    ###########################################################################
    # test_throttle_sync
    ###########################################################################
    def test_throttle_sync(self,
                           requests_arg: int,
                           seconds_arg: Union[int, float],
                           early_count_arg: int,
                           send_interval_mult_arg: float
                           ) -> None:
        """Method to start throttle sync tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            early_count_arg: count used for sync with early count algo
            send_interval_mult_arg: interval between each send of a request
        """
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        self.throttle_router(requests=requests_arg,
                             seconds=seconds_arg,
                             mode=Throttle.MODE_SYNC_EC,
                             early_count=0,
                             lb_threshold=0,
                             shutdown_check=None,
                             send_interval=send_interval)

    ###########################################################################
    # test_throttle_sync_ec
    ###########################################################################
    def test_throttle_sync_ec(self,
                              requests_arg: int,
                              seconds_arg: Union[int, float],
                              early_count_arg: int,
                              send_interval_mult_arg: float
                              ) -> None:
        """Method to start throttle sync_ec tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            early_count_arg: count used for sync with early count algo
            send_interval_mult_arg: interval between each send of a request
        """
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        self.throttle_router(requests=requests_arg,
                             seconds=seconds_arg,
                             mode=Throttle.MODE_SYNC_EC,
                             early_count=early_count_arg,
                             lb_threshold=0,
                             shutdown_check=None,
                             send_interval=send_interval)

    ###########################################################################
    # test_throttle_sync_lb
    ###########################################################################
    def test_throttle_sync_lb(self,
                              requests_arg: int,
                              seconds_arg: Union[int, float],
                              lb_threshold_arg: Union[int, float],
                              send_interval_mult_arg: float
                              ) -> None:
        """Method to start throttle sync_lb tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            lb_threshold_arg: threshold used with sync leaky bucket algo
            send_interval_mult_arg: interval between each send of a request
        """
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        self.throttle_router(requests=requests_arg,
                             seconds=seconds_arg,
                             mode=Throttle.MODE_SYNC_LB,
                             early_count=0,
                             lb_threshold=lb_threshold_arg,
                             shutdown_check=None,
                             send_interval=send_interval)


    ###########################################################################
    # test_throttle_async
    ###########################################################################
    def test_pie_throttle_async(self,
                                requests_arg: int,
                                seconds_arg: Union[int, float],
                                shutdown_check_arg: Union[None,
                                                          Callable[[], bool]],
                                send_interval_mult_arg: float
                                ) -> None:
        """Method to start throttle mode1 tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            shutdown_check_arg: function to call to check for shutdown
            send_interval_mult_arg: interval between each send of a request
        """
        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_multiplier = 100
        send_interval = (seconds_arg/requests_arg) * send_interval_mult_arg
        request_validator = RequestValidator(requests=requests_arg,
                                             seconds=seconds_arg,
                                             mode=Throttle.MODE_ASYNC,
                                             early_count=0,
                                             lb_threshold=0,
                                             shutdown_check=shutdown_check_arg,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Decorate functions with throttle
        #######################################################################
        if shutdown_check_arg:
            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC,
                      shutdown_check=shutdown_check_arg)
            def f0():
                request_validator.callback0()

            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC,
                      shutdown_check=shutdown_check_arg)
            def f1(idx):
                request_validator.callback1(idx)

            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC,
                      shutdown_check=shutdown_check_arg)
            def f2(idx, requests):
                request_validator.callback2(idx, requests)

            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC,
                      shutdown_check=shutdown_check_arg)
            def f3(*, idx):
                request_validator.callback3(idx=idx)

            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC,
                      shutdown_check=shutdown_check_arg)
            def f4(*, idx, seconds):
                request_validator.callback4(idx=idx, seconds=seconds)

            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC,
                      shutdown_check=shutdown_check_arg)
            def f5(idx,*, interval):
                request_validator.callback5(idx,
                                                  interval=interval)

            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC,
                      shutdown_check=shutdown_check_arg)
            def f6(idx, requests, *, seconds, interval):
                request_validator.callback6(idx,
                                                  requests,
                                                  seconds=seconds,
                                                  interval=interval)
        else:
            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC)
            def f0():
                request_validator.callback0()

            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC)
            def f1(idx):
                request_validator.callback1(idx)

            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC)
            def f2(idx, requests):
                request_validator.callback2(idx, requests)

            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC)
            def f3(*, idx):
                request_validator.callback3(idx=idx)

            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC)
            def f4(*, idx, seconds):
                request_validator.callback4(idx=idx, seconds=seconds)

            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC)
            def f5(idx, *, interval):
                request_validator.callback5(idx,
                                                  interval=interval)

            @throttle(requests=requests_arg,
                      seconds=seconds_arg,
                      mode=Throttle.MODE_ASYNC)
            def f6(idx, requests, *, seconds, interval):
                request_validator.callback6(idx,
                                                  requests,
                                                  seconds=seconds,
                                                  interval=interval)

        #######################################################################
        # Invoke the functions
        #######################################################################
        for i in range(requests_arg * request_multiplier):
            rc = f0()
            assert rc is None
            time.sleep(send_interval)

            rc = f1(i)
            assert rc is None
            time.sleep(send_interval)

            rc = f2(i, requests_arg)
            assert rc is None
            time.sleep(send_interval)

            rc = f3(idx=i)
            assert rc is None
            time.sleep(send_interval)

            rc = f4(idx=i, seconds=seconds_arg)
            assert rc is None
            time.sleep(send_interval)

            rc = f5(idx=i, interval=send_interval_mult_arg)
            assert rc is None
            time.sleep(send_interval)

            rc = f6(i, requests_arg,
                    seconds=seconds_arg, interval=send_interval_mult_arg)
            assert rc is None
            time.sleep(send_interval)

        request_validator.validate_series()  # validate for the series

    ###########################################################################
    # test_throttle_sync
    ###########################################################################
    def test_pie_throttle_sync(self,
                               requests_arg: int,
                               seconds_arg: Union[int, float],
                               send_interval_mult_arg: float
                               ) -> None:
        """Method to start throttle sync tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            send_interval_mult_arg: interval between each send of a request
        """
        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_multiplier = 100
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        request_validator = RequestValidator(requests=requests_arg,
                                             seconds=seconds_arg,
                                             mode=Throttle.MODE_SYNC,
                                             early_count=0,
                                             lb_threshold=0,
                                             shutdown_check=None,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Decorate functions with throttle
        #######################################################################
        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f0():
            request_validator.callback0()
            return 42

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f1(idx):
            request_validator.callback1(idx)
            return idx + 42 + 1

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f2(idx, requests):
            request_validator.callback2(idx, requests)
            return idx + 42 + 2

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f3(*, idx):
            request_validator.callback3(idx=idx)
            return idx + 42 + 3

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f4(*, idx, seconds):
            request_validator.callback4(idx=idx, seconds=seconds)
            return idx + 42 + 4

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f5(idx, *, interval):
            request_validator.callback5(idx,
                                              interval=interval)
            return idx + 42 + 5

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f6(idx, requests, *, seconds, interval):
            request_validator.callback6(idx,
                                              requests,
                                              seconds=seconds,
                                              interval=interval)
            return idx + 42 + 6

        #######################################################################
        # Invoke the functions
        #######################################################################
        for i in range(requests_arg * request_multiplier):
            rc = f0()
            assert rc == 0
            time.sleep(send_interval)

            rc = f1(i)
            assert rc == i + 42 + 1
            time.sleep(send_interval)

            rc = f2(i, requests_arg)
            assert rc == i + 42 + 2
            time.sleep(send_interval)

            rc = f3(idx=i)
            assert rc == i + 42 + 3
            time.sleep(send_interval)

            rc = f4(idx=i, seconds=seconds_arg)
            assert rc == i + 42 + 4
            time.sleep(send_interval)

            rc = f5(idx=i, interval=send_interval_mult_arg)
            assert rc == i + 42 + 5
            time.sleep(send_interval)

            rc = f6(i, requests_arg,
                    seconds=seconds_arg, interval=send_interval_mult_arg)
            assert rc == i + 42 + 6
            time.sleep(send_interval)

        request_validator.validate_series()  # validate for the series

    ###########################################################################
    # test_throttle_sync_ec
    ###########################################################################
    def test_pie_throttle_sync_ec(self,
                                  requests_arg: int,
                                  seconds_arg: Union[int, float],
                                  early_count_arg: int,
                                  send_interval_mult_arg: float
                                ) -> None:
        """Method to start throttle sync_ec tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            early_count_arg: count used for sync with early count algo
            send_interval_mult_arg: interval between each send of a request
        """
        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_multiplier = 100
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        request_validator = RequestValidator(requests=requests_arg,
                                             seconds=seconds_arg,
                                             mode=Throttle.MODE_SYNC_EC,
                                             early_count=early_count_arg,
                                             lb_threshold=0,
                                             shutdown_check=None,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Decorate functions with throttle
        #######################################################################
        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f0():
            request_validator.callback0()
            return 42

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f1(idx):
            request_validator.callback1(idx)
            return idx + 42 + 1

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f2(idx, requests):
            request_validator.callback2(idx, requests)
            return idx + 42 + 2

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f3(*, idx):
            request_validator.callback3(idx=idx)
            return idx + 42 + 3

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f4(*, idx, seconds):
            request_validator.callback4(idx=idx, seconds=seconds)
            return idx + 42 + 4

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f5(idx, *, interval):
            request_validator.callback5(idx,
                                              interval=interval)
            return idx + 42 + 5

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f6(idx, requests, *, seconds, interval):
            request_validator.callback6(idx,
                                              requests,
                                              seconds=seconds,
                                              interval=interval)
            return idx + 42 + 6

        #######################################################################
        # Invoke the functions
        #######################################################################
        for i in range(requests_arg * request_multiplier):
            rc = f0()
            assert rc == 0
            time.sleep(send_interval)

            rc = f1(i)
            assert rc == i + 42 + 1
            time.sleep(send_interval)

            rc = f2(i, requests_arg)
            assert rc == i + 42 + 2
            time.sleep(send_interval)

            rc = f3(idx=i)
            assert rc == i + 42 + 3
            time.sleep(send_interval)

            rc = f4(idx=i, seconds=seconds_arg)
            assert rc == i + 42 + 4
            time.sleep(send_interval)

            rc = f5(idx=i, interval=send_interval_mult_arg)
            assert rc == i + 42 + 5
            time.sleep(send_interval)

            rc = f6(i, requests_arg,
                    seconds=seconds_arg, interval=send_interval_mult_arg)
            assert rc == i + 42 + 6
            time.sleep(send_interval)

        request_validator.validate_series()  # validate for the series

    ###########################################################################
    # test_throttle_sync_lb
    ###########################################################################
    def test_pie_throttle_sync_lb(self,
                                  requests_arg: int,
                                  seconds_arg: Union[int, float],
                                  lb_threshold_arg: Union[int, float],
                                  send_interval_mult_arg: float
                                  ) -> None:
        """Method to start throttle sync_lb tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            lb_threshold_arg: threshold used with sync leaky bucket algo
            send_interval_mult_arg: interval between each send of a request
        """
        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_multiplier = 100
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        request_validator = RequestValidator(requests=requests_arg,
                                             seconds=seconds_arg,
                                             mode=Throttle.MODE_SYNC_LB,
                                             early_count=0,
                                             lb_threshold=lb_threshold_arg,
                                             shutdown_check=None,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Decorate functions with throttle
        #######################################################################
        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f0():
            request_validator.callback0()
            return 42

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f1(idx):
            request_validator.callback1(idx)
            return idx + 42 + 1

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f2(idx, requests):
            request_validator.callback2(idx, requests)
            return idx + 42 + 2

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f3(*, idx):
            request_validator.callback3(idx=idx)
            return idx + 42 + 3

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f4(*, idx, seconds):
            request_validator.callback4(idx=idx, seconds=seconds)
            return idx + 42 + 4

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f5(idx, *, interval):
            request_validator.callback5(idx,
                                              interval=interval)
            return idx + 42 + 5

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f6(idx, requests, *, seconds, interval):
            request_validator.callback6(idx,
                                              requests,
                                              seconds=seconds,
                                              interval=interval)
            return idx + 42 + 6

        #######################################################################
        # Invoke the functions
        #######################################################################
        for i in range(requests_arg * request_multiplier):
            rc = f0()
            assert rc == 0
            time.sleep(send_interval)

            rc = f1(i)
            assert rc == i + 42 + 1
            time.sleep(send_interval)

            rc = f2(i, requests_arg)
            assert rc == i + 42 + 2
            time.sleep(send_interval)

            rc = f3(idx=i)
            assert rc == i + 42 + 3
            time.sleep(send_interval)

            rc = f4(idx=i, seconds=seconds_arg)
            assert rc == i + 42 + 4
            time.sleep(send_interval)

            rc = f5(idx=i, interval=send_interval_mult_arg)
            assert rc == i + 42 + 5
            time.sleep(send_interval)

            rc = f6(i, requests_arg,
                    seconds=seconds_arg, interval=send_interval_mult_arg)
            assert rc == i + 42 + 6
            time.sleep(send_interval)

        request_validator.validate_series()  # validate for the series

    ###########################################################################
    # throttle_router
    ###########################################################################
    def throttle_router(self,
                        requests: int,
                        seconds: Union[int, float],
                        mode: int,
                        early_count: int,
                        lb_threshold: Union[int, float],
                        shutdown_check: Union[None, Callable[[], bool]],
                        send_interval: float
                        ) -> None:
        """Method test_throttle_router.

        Args:
            requests: number of requests per interval
            seconds: interval for number of requests
            mode: async or sync_EC or sync_LB
            early_count: count used for sync with early count algo
            lb_threshold: threshold used with sync leaky bucket algo
            shutdown_check: function to call to check for shutdown
            send_interval: interval between each send of a request
        """
        request_multiplier = 100
        #######################################################################
        # Instantiate Throttle
        #######################################################################
        if mode == Throttle.MODE_ASYNC:
            if shutdown_check:
                a_throttle = Throttle(requests=requests,
                                      seconds=seconds,
                                      mode=Throttle.MODE_ASYNC,
                                      shutdown_check=shutdown_check
                                      )
            else:
                a_throttle = Throttle(requests=requests,
                                      seconds=seconds,
                                      mode=Throttle.MODE_ASYNC
                                      )
        elif mode  == Throttle.MODE_SYNC:
            a_throttle = Throttle(requests=requests,
                                  seconds=seconds,
                                  mode=Throttle.MODE_SYNC
                                  )
        elif mode  == Throttle.MODE_SYNC_EC:
            a_throttle = Throttle(requests=requests,
                                  seconds=seconds,
                                  mode=Throttle.MODE_SYNC_EC,
                                  early_count=early_count
                                  )
        elif mode == Throttle.MODE_SYNC_LB:
            a_throttle = Throttle(requests=requests,
                                  seconds=seconds,
                                  mode=Throttle.MODE_SYNC_LB,
                                  lb_threshold=lb_threshold
                                  )
        else:
            raise InvalidModeNum('The Mode must be 1, 2, 3, or 4')

        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_validator = RequestValidator(requests=requests,
                                             seconds=seconds,
                                             mode=mode,
                                             early_count=early_count,
                                             lb_threshold=lb_threshold,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Make requests and validate
        #######################################################################

        for i in range(requests * request_multiplier):
            # 0
            rc = a_throttle.send_request(request_validator.request0)
            assert rc == i if mode!=Throttle.MODE_ASYNC else None
            time.sleep(send_interval)

            # 1
            rc = a_throttle.send_request(request_validator.request1, i)
            assert rc == i if mode!=Throttle.MODE_ASYNC else None
            time.sleep(send_interval)

            # 2
            rc = a_throttle.send_request(request_validator.request2,
                                         i,
                                         requests)
            assert rc == i if mode!=Throttle.MODE_ASYNC else None
            time.sleep(send_interval)

            # 3
            rc = a_throttle.send_request(request_validator.request3, idx=i)
            assert rc == i if mode!=Throttle.MODE_ASYNC else None
            time.sleep(send_interval)

            # 4
            rc = a_throttle.send_request(request_validator.request4,
                                         idx=i,
                                         seconds=seconds)
            assert rc == i if mode!=Throttle.MODE_ASYNC else None
            time.sleep(send_interval)

            # 5
            rc = a_throttle.send_request(request_validator.request5,
                                         i,
                                         interval=send_interval)
            assert rc == i if mode!=Throttle.MODE_ASYNC else None
            time.sleep(send_interval)

            # 6
            rc = a_throttle.send_request(request_validator.request6,
                                         i,
                                         requests,
                                         seconds=seconds,
                                         interval=send_interval)
            assert rc == i if mode!=Throttle.MODE_ASYNC else None
            time.sleep(send_interval)

        request_validator.validate_series()  # validate for the series

###############################################################################
# RequestValidator class
###############################################################################
class RequestValidator:
    def __init__(self,
                 requests,
                 seconds,
                 mode,
                 early_count,
                 lb_threshold,
                 shutdown_check,
                 request_mult,
                 send_interval) -> None:
        self.requests = requests
        self.seconds = seconds
        self.mode = mode
        self.early_count = early_count
        self.lb_threshold = lb_threshold
        self.shutdown_check = shutdown_check
        self.request_mult = request_mult
        self.send_interval = send_interval
        self.idx = -1
        self.req_times = []
        self.normalized_times = []
        self.normalized_intervals = []
        self.mean_interval = 0

        # calculate parms

        self.total_requests = requests * request_mult
        self.target_interval = seconds / requests
        self.max_interval = max(self.target_interval,
                                self.send_interval)
        self.min_interval = min(self.target_interval,
                                self.send_interval)

        self.target_interval_1pct = self.target_interval * 0.01
        self.target_interval_5pct = self.target_interval * 0.05
        self.target_interval_10pct = self.target_interval * 0.10

        self.max_interval_1pct = self.max_interval * 0.01
        self.max_interval_5pct = self.max_interval * 0.05
        self.max_interval_10pct = self.max_interval * 0.10

        self.min_interval_1pct = self.min_interval * 0.01
        self.min_interval_5pct = self.min_interval * 0.05
        self.min_interval_10pct = self.min_interval * 0.10




    def validate_series(self):
        """Validate the requests."""
        assert len(self.req_times) == self.total_requests
        base_time = self.req_times[0][1]
        prev_time = base_time
        for idx, req_item in enumerate(self.req_times):
            assert idx == req_item[0]
            cur_time = req_item[1]
            self.normalized_times.append(cur_time - base_time)
            self.normalized_intervals.append(cur_time - prev_time)
            prev_time = cur_time

        self.mean_interval = self.normalized_times[-1]/(self.total_requests-1)


        if ((self.mode == Throttle.MODE_ASYNC) or
                (self.mode == Throttle.MODE_SYNC) or
                (self.target_interval <= self.send_interval)):
            self.validate_async_sync()
        elif self.mode == Throttle.MODE_SYNC_EC:
            self.validate_sync_ec()
        elif self.mode == Throttle.MODE_SYNC_LB:
            self.validate_sync_lb()
        else:
            raise InvalidModeNum('Mode must be 1, 2, 3, or 4')

    def validate_async_sync(self):
        num_early = 0
        num_early_1pct = 0
        num_early_5pct = 0
        num_early_10pct = 0

        num_late = 0
        num_late_1pct = 0
        num_late_5pct = 0
        num_late_10pct = 0

        for interval in self.normalized_intervals[1:]:
            if interval < self.target_interval:
                num_early += 1
            if interval < self.target_interval - self.target_interval_1pct:
                num_early_1pct += 1
            if interval < self.target_interval - self.target_interval_5pct:
                num_early_5pct += 1
            if interval < self.target_interval - self.target_interval_10pct:
                num_early_10pct += 1

            if self.max_interval < interval:
                num_late += 1
            if self.max_interval + self.max_interval_1pct < interval:
                num_late_1pct += 1
            if self.max_interval + self.max_interval_5pct < interval:
                num_late_5pct += 1
            if self.max_interval + self.max_interval_10pct < interval:
                num_late_10pct += 1

        print('num_requests_sent1:', self.total_requests)
        print('num_early1:', num_early)
        print('num_early_1pct1:', num_early_1pct)
        print('num_early_5pct1:', num_early_5pct)
        print('num_early_10pct1:', num_early_10pct)

        print('num_late1:', num_late)
        print('num_late_1pct1:', num_late_1pct)
        print('num_late_5pct1:', num_late_5pct)
        print('num_late_10pct1:', num_late_10pct)

        assert num_early_10pct == 0
        # assert num_early_5pct == 0
        # assert num_early_1pct == 0

        if self.target_interval < self.send_interval:
            assert num_early == 0

        assert num_late_10pct == 0
        # assert num_late_5pct == 0
        # assert num_late_1pct == 0
        # assert num_late == 0

        assert self.max_interval <= self.mean_interval


    def validate_sync_ec(self):
        num_short_early = 0
        num_short_early_1pct = 0
        num_short_early_5pct = 0
        num_short_early_10pct = 0

        num_short_late = 0
        num_short_late_1pct = 0
        num_short_late_5pct = 0
        num_short_late_10pct = 0

        num_long_early = 0
        num_long_early_1pct = 0
        num_long_early_5pct = 0
        num_long_early_10pct = 0

        num_long_late = 0
        num_long_late_1pct = 0
        num_long_late_5pct = 0
        num_long_late_10pct = 0

        long_interval = (((self.early_count + 1) * self.target_interval)
                         - (self.early_count * self.min_interval))

        for idx, interval in enumerate(self.normalized_intervals[1:], 1):
            if idx % (self.early_count + 1):  # if long interval expected
                if interval < long_interval:
                    num_long_early += 1
                if interval < long_interval - self.target_interval_1pct:
                    num_long_early_1pct += 1
                if interval < long_interval - self.target_interval_5pct:
                    num_long_early_5pct += 1
                if interval < (long_interval - self.target_interval_10pct):
                    num_long_early_10pct += 1

                if self.max_interval < interval:
                    num_long_late += 1
                if self.max_interval + self.max_interval_1pct < interval:
                    num_long_late_1pct += 1
                if self.max_interval + self.max_interval_5pct < interval:
                    num_long_late_5pct += 1
                if self.max_interval + self.max_interval_10pct < interval:
                    num_long_late_10pct += 1
            else:
                if interval < self.min_interval:
                    num_short_early += 1
                if interval < self.min_interval - self.min_interval_1pct:
                    num_short_early_1pct += 1
                if interval < self.min_interval - self.min_interval_5pct:
                    num_short_early_5pct += 1
                if interval < (self.min_interval - self.min_interval_10pct):
                    num_short_early_10pct += 1

                if self.min_interval < interval:
                    num_short_late += 1
                if self.min_interval + self.min_interval_1pct < interval:
                    num_short_late_1pct += 1
                if self.min_interval + self.min_interval_5pct < interval:
                    num_short_late_5pct += 1
                if self.min_interval + self.min_interval_10pct < interval:
                    num_short_late_10pct += 1

        print('num_requests_sent2:', self.total_requests)
        print('num_early2:', num_long_early)
        print('num_early_1pct2:', num_long_early_1pct)
        print('num_early_5pct2:', num_long_early_5pct)
        print('num_early_10pct2:', num_long_early_10pct)

        print('num_late2:', num_long_late)
        print('num_late_1pct2:', num_long_late_1pct)
        print('num_late_5pct2:', num_long_late_5pct)
        print('num_late_10pct2:', num_long_late_10pct)

        print('num_early2:', num_short_early)
        print('num_early_1pct2:', num_short_early_1pct)
        print('num_early_5pct2:', num_short_early_5pct)
        print('num_early_10pct2:', num_short_early_10pct)

        print('num_late2:', num_short_late)
        print('num_late_1pct2:', num_short_late_1pct)
        print('num_late_5pct2:', num_short_late_5pct)
        print('num_late_10pct2:', num_short_late_10pct)

        assert num_long_early_10pct == 0
        # assert num_long_early_5pct == 0
        # assert num_long_early_5pct == 0
        # assert num_long_early == 0

        assert num_long_late_10pct == 0
        # assert num_long_late_5pct == 0
        # assert num_long_late_1pct == 0
        # assert num_long_late == 0

        assert num_short_early_10pct == 0
        # assert num_short_early_5pct == 0
        # assert num_short_early_5pct == 0
        # assert num_short_early == 0

        assert num_short_late_10pct == 0
        # assert num_short_late_5pct == 0
        # assert num_short_late_1pct == 0
        # assert num_short_late == 0

        assert self.target_interval <= self.mean_interval

    def validate_sync_lb(self):
        amt_added_per_send = self.target_interval - self.send_interval
        num_sends_before_trigger = (math.floor(self.lb_threshold /
                                               amt_added_per_send))
        amt_remaining_in_bucket = (self.lb_threshold
                                   - (num_sends_before_trigger
                                      * self.send_interval))
        amt_over = self.send_interval - amt_remaining_in_bucket



        trigger_interval = self.send_interval + amt_over
        trigger_interval_1pct = trigger_interval * 0.01
        trigger_interval_5pct = trigger_interval * 0.05
        trigger_interval_10pct = trigger_interval * 0.10



        num_short_early = 0
        num_short_early_1pct = 0
        num_short_early_5pct = 0
        num_short_early_10pct = 0

        num_short_late = 0
        num_short_late_1pct = 0
        num_short_late_5pct = 0
        num_short_late_10pct = 0

        num_trigger_early = 0
        num_trigger_early_1pct = 0
        num_trigger_early_5pct = 0
        num_trigger_early_10pct = 0

        num_trigger_late = 0
        num_trigger_late_1pct = 0
        num_trigger_late_5pct = 0
        num_trigger_late_10pct = 0

        num_early = 0
        num_early_1pct = 0
        num_early_5pct = 0
        num_early_10pct = 0

        num_late = 0
        num_late_1pct = 0
        num_late_5pct = 0
        num_late_10pct = 0

        for idx, interval in enumerate(self.normalized_intervals[1:], 1):
            if idx <= num_sends_before_trigger:
                if interval < self.min_interval:
                    num_short_early += 1
                if interval < self.min_interval - self.min_interval_1pct:
                    num_short_early_1pct += 1
                if interval < self.min_interval - self.min_interval_5pct:
                    num_short_early_5pct += 1
                if interval < (self.min_interval - self.min_interval_10pct):
                    num_short_early_10pct += 1

                if self.min_interval < interval:
                    num_short_late += 1
                if self.min_interval + self.min_interval_1pct < interval:
                    num_short_late_1pct += 1
                if self.min_interval + self.min_interval_5pct < interval:
                    num_short_late_5pct += 1
                if self.min_interval + self.min_interval_10pct < interval:
                    num_short_late_10pct += 1
            elif idx == num_sends_before_trigger + 1:
                if interval < trigger_interval:
                    num_trigger_early += 1
                if interval < trigger_interval - trigger_interval_1pct:
                    num_trigger_early_1pct += 1
                if interval < trigger_interval - trigger_interval_5pct:
                    num_trigger_early_5pct += 1
                if interval < trigger_interval - trigger_interval_10pct:
                    num_trigger_early_10pct += 1

                if trigger_interval < interval:
                    num_trigger_late += 1
                if trigger_interval + trigger_interval_1pct < interval:
                    num_trigger_late_1pct += 1
                if trigger_interval + trigger_interval_5pct < interval:
                    num_trigger_late_5pct += 1
                if trigger_interval + trigger_interval_10pct < interval:
                    num_trigger_late_10pct += 1
            else:
                if interval < self.target_interval:
                    num_early += 1
                if interval < self.target_interval - self.target_interval_1pct:
                    num_early_1pct += 1
                if interval < self.target_interval - self.target_interval_5pct:
                    num_early_5pct += 1
                if interval < self.target_interval - \
                        self.target_interval_10pct:
                    num_early_10pct += 1

                if self.max_interval < interval:
                    num_late += 1
                if self.max_interval + self.max_interval_1pct < interval:
                    num_late_1pct += 1
                if self.max_interval + self.max_interval_5pct < interval:
                    num_late_5pct += 1
                if self.max_interval + self.max_interval_10pct < interval:
                    num_late_10pct += 1

        print('num_requests_sent3:', self.total_requests)

        print('num_short_early3:' ,num_short_early)
        print('num_short_early_1pct3:', num_short_early_1pct)
        print('num_short_early_5pct3:', num_short_early_5pct)
        print('num_short_early_10pct3:', num_short_early_10pct)

        print('num_short_late3:', num_short_late)
        print('num_short_late_1pct3:', num_short_late_1pct)
        print('num_short_late_5pct3:', num_short_late_5pct)
        print('num_short_late_10pct3:', num_short_late_10pct)

        print('num_trigger_early3:', num_trigger_early)
        print('num_trigger_early_1pct3:', num_trigger_early_1pct)
        print('num_trigger_early_5pct3:', num_trigger_early_5pct)
        print('num_trigger_early_10pct3:', num_trigger_early_10pct)

        print('num_trigger_late3:', num_trigger_late)
        print('num_trigger_late_1pct3:', num_trigger_late_1pct)
        print('num_trigger_late_5pct3:', num_trigger_late_5pct)
        print('num_trigger_late_10pct3:', num_trigger_late_10pct)

        print('num_early3:', num_early)
        print('num_early_1pct3:', num_early_1pct)
        print('num_early_5pct3:', num_early_5pct)
        print('num_early_10pct3:', num_early_10pct)

        print('num_late3:', num_late)
        print('num_late_1pct3:', num_late_1pct)
        print('num_late_5pct3:', num_late_5pct)
        print('num_late_10pct3:', num_late_10pct)

        assert num_short_early_10pct == 0
        assert num_short_late_10pct == 0

        assert num_trigger_early_10pct == 0
        assert num_trigger_late_10pct == 0

        assert num_early_10pct == 0
        assert num_late_10pct == 0

        exp_mean_interval = ((self.send_interval * num_sends_before_trigger)
                             + trigger_interval
                             + (self.target_interval
                                * (self.total_requests
                                   - (num_sends_before_trigger + 1)))
                             ) / (self.total_requests - 1)

        assert exp_mean_interval <= self.mean_interval

    def request0(self) -> int:
        """Request0 target.

        Returns:
            the index reflected back
        """
        self.idx += 1
        self.req_times.append((self.idx, time()))
        return self.idx

    def request1(self, idx: int) -> int:
        """Request1 target.

        Args:
            idx: the index of the call

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time()))
        assert idx == self.idx + 1
        self.idx = idx
        return idx

    def request2(self, idx: int, requests: int) -> int:
        """Request2 target.

        Args:
            idx: the index of the call
            requests: number of requests for the throttle

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time()))
        assert idx == self.idx + 1
        assert requests == self.requests
        self.idx = idx
        return idx

    def request3(self, *, idx: int) -> int:
        """Request3 target.

        Args:
            idx: the index of the call

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time()))
        assert idx == self.idx + 1
        self.idx = idx
        return idx

    def request4(self, *, idx: int, seconds: int) -> int:
        """Request4 target.

        Args:
            idx: the index of the call
            seconds: number of seconds for the throttle

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time()))
        assert idx == self.idx + 1
        assert seconds == self.seconds
        self.idx = idx
        return idx

    def request5(self, idx: int, *, interval: float) -> int:
        """Request5 target.

        Args:
            idx: the index of the call
            interval: the interval used between requests

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time()))
        assert idx == self.idx + 1
        assert interval == self.send_interval
        self.idx = idx
        return idx

    def request6(self,
                 idx: int,
                 requests: int,
                 *,
                 seconds: int,
                 interval: float) -> int:
        """Request5 target.

         Args:
            idx: the index of the call
            requests: number of requests for the throttle
            seconds: number of seconds for the throttle
            interval: the interval used between requests

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time()))
        assert idx == self.idx + 1
        assert requests == self.requests
        assert seconds == self.seconds
        assert interval == self.send_interval
        self.idx = idx
        return idx

    ###########################################################################
    # Queue callback targets
    ###########################################################################
    def callback0(self) -> None:
        """Queue the callback for request0."""
        self.idx += 1
        self.req_times.append((self.idx, time()))

    def callback1(self, idx: int) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
        """
        self.req_times.append((idx, time()))
        assert idx == self.idx + 1
        self.idx = idx

    def callback2(self, idx: int, requests: int) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
            requests: number of requests for the throttle
        """
        self.req_times.append((idx, time()))
        assert idx == self.idx + 1
        assert requests == self.requests
        self.idx = idx

    def callback3(self, *, idx: int):
        """Queue the callback for request0.

        Args:
            idx: index of the request call
        """
        self.req_times.append((idx, time()))
        assert idx == self.idx + 1
        self.idx = idx

    def callback4(self, *, idx: int, seconds: int) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
            seconds: number of seconds for the throttle
        """
        self.req_times.append((idx, time()))
        assert idx == self.idx + 1
        assert seconds == self.seconds
        self.idx = idx

    def callback5(self,
                        idx: int,
                        *,
                        interval: float) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
            interval: interval between requests
        """
        self.req_times.append((idx, time()))
        assert idx == self.idx + 1
        assert interval == self.send_interval
        self.idx = idx

    def callback6(self,
                        idx: int,
                        requests: int,
                        *,
                        seconds: int,
                        interval: float) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
            requests: number of requests for the throttle
            seconds: number of seconds for the throttle
            interval: interval between requests
        """
        self.req_times.append((idx, time()))
        assert idx == self.idx + 1
        assert requests == self.requests
        assert seconds == self.seconds
        assert interval == self.send_interval
        self.idx = idx


###############################################################################
# TestThrottleDocstrings class
###############################################################################
class TestThrottleDocstrings:
    """Class TestThrottleDocstrings."""
    def test_throttle_with_example_1(self) -> None:
        """Method test_throttle_with_example_1."""
        flowers('Example for README:')

        from time import time
        from scottbrian_utils.throttle import throttle
        @throttle(requests=3, seconds=1, mode=Throttle.SYNC_MODE)
        def make_request(i, previous_arrival_time):
            arrival_time = time()
            if i == 0:
                previous_arrival_time = arrival_time
            interval = arrival_time - previous_arrival_time
            print(f'request {i} interval from previous: {interval:0.2f} '
                  f'seconds'
            return arrival_time

        previous_time = 0
        for i in range(10):
            previous_time = make_request(i, previous_time)

    # def test_throttle_with_example_2(self) -> None:
    #     """Method test_throttle_with_example_2."""
    #     print()
    #     print('#' * 50)
    #     print('Example for throttle decorator:')
    #     print()
    #
    #     @throttle(file=sys.stdout)
    #     def func2() -> None:
    #         print('2 * 3 =', 2*3)
    #
    #     func2()
    #
    # def test_throttle_with_example_3(self) -> None:
    #     """Method test_throttle_with_example_3."""
    #     print()
    #     print('#' * 50)
    #     print('Example of printing to stderr:')
    #     print()
    #
    #     @throttle(file=sys.stderr)
    #     def func3() -> None:
    #         print('this text printed to stdout, not stderr')
    #
    #     func3()
    #
    # def test_throttle_with_example_4(self) -> None:
    #     """Method test_throttle_with_example_4."""
    #     print()
    #     print('#' * 50)
    #     print('Example of statically wrapping function with throttle:')
    #     print()
    #
    #     _tbe = False
    #
    #     @throttle(throttle_enabled=_tbe, file=sys.stdout)
    #     def func4a() -> None:
    #         print('this is sample text for _tbe = False static example')
    #
    #     func4a()  # func4a is not wrapped by time box
    #
    #     _tbe = True
    #
    #     @throttle(throttle_enabled=_tbe, file=sys.stdout)
    #     def func4b() -> None:
    #         print('this is sample text for _tbe = True static example')
    #
    #     func4b()  # func4b is wrapped by time box
    #
    # def test_throttle_with_example_5(self) -> None:
    #     """Method test_throttle_with_example_5."""
    #     print()
    #     print('#' * 50)
    #     print('Example of dynamically wrapping function with throttle:')
    #     print()
    #
    #     _tbe = True
    #     def tbe() -> bool: return _tbe
    #
    #     @throttle(throttle_enabled=tbe, file=sys.stdout)
    #     def func5() -> None:
    #         print('this is sample text for the tbe dynamic example')
    #
    #     func5()  # func5 is wrapped by time box
    #
    #     _tbe = False
    #     func5()  # func5 is not wrapped by throttle
    #
    # def test_throttle_with_example_6(self) -> None:
    #     """Method test_throttle_with_example_6."""
    #     print()
    #     print('#' * 50)
    #     print('Example of using different datetime format:')
    #     print()
    #
    #     a_datetime_format: DT_Format = cast(DT_Format, '%m/%d/%y %H:%M:%S')
    #
    #     @throttle(dt_format=a_datetime_format)
    #     def func6() -> None:
    #         print('this is sample text for the datetime format example')
    #
    #     func6()
