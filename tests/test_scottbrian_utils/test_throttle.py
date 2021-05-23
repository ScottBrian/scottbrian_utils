"""test_throttle.py module."""

import pytest
import time
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
mode_arg_list = [Throttle.ASYNC_MODE,
                 Throttle.SYNC_MODE_LB,
                 Throttle.SYNC_MODE_EC]


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
lb_threshold_arg_list = [0, 0.1, 1, 1.5, 2, 3]


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
early_count_arg_list = [0, 1, 2, 3]


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
# send_interval_arg fixture
###############################################################################
send_interval_arg_list = [-1.0, 0.0, 0.1, 0.2, 0.3, 0.5, 0.9, 1.0, 1.1]


@pytest.fixture(params=send_interval_arg_list)  # type: ignore
def send_interval_arg(request: Any) -> float:
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
                         mode=1)
        with pytest.raises(IncorrectRequestsSpecified):
            _ = Throttle(requests=-1,
                         seconds=1,
                         mode=1)
        with pytest.raises(IncorrectRequestsSpecified):
            _ = Throttle(requests='1',  # type: ignore
                         seconds=1,
                         mode=1)

        #######################################################################
        # bad seconds
        #######################################################################
        with pytest.raises(IncorrectSecondsSpecified):
            _ = Throttle(requests=1,
                         seconds=0,
                         mode=1)
        with pytest.raises(IncorrectSecondsSpecified):
            _ = Throttle(requests=1,
                         seconds=-1,
                         mode=1)
        with pytest.raises(IncorrectSecondsSpecified):
            _ = Throttle(requests=1,
                         seconds='1',  # type: ignore
                         mode=1)

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
                         mode=4)
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
                         mode=Throttle.ASYNC_MODE,
                         early_count=0)  # not allowed with mode 1
        with pytest.raises(MissingEarlyCountSpecification):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.SYNC_MODE_EC)
        with pytest.raises(EarlyCountNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.SYNC_MODE_LB,
                         early_count=1)  # not allowed with mode 3
        with pytest.raises(IncorrectEarlyCountSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.SYNC_MODE_EC,
                         early_count=-1)
        with pytest.raises(IncorrectEarlyCountSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.SYNC_MODE_EC,
                         early_count='1')  # type: ignore
        #######################################################################
        # bad lb_threshold
        #######################################################################
        with pytest.raises(LbThresholdNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.ASYNC_MODE,
                         lb_threshold=1)  # not allowed with mode 1
        with pytest.raises(LbThresholdNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.SYNC_MODE_EC,
                         lb_threshold=0)  # not allowed with mode 2
        with pytest.raises(MissingLbThresholdSpecification):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.SYNC_MODE_LB)
        with pytest.raises(IncorrectLbThresholdSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=2,
                         lb_threshold=-1)
        with pytest.raises(IncorrectLbThresholdSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=2,
                         lb_threshold='1')  # type: ignore

        #######################################################################
        # bad shut_down  (no missing check since shutdown_check is optional)
        #######################################################################
        with pytest.raises(IncorrectShutdownCheckSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.ASYNC_MODE,
                         shutdown_check=1)  # type: ignore
        with pytest.raises(IncorrectShutdownCheckSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.ASYNC_MODE,
                         shutdown_check='1')  # type: ignore
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
                              mode=1)

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
    # repr with mode 1 async
    ###########################################################################
    def test_throttle_repr_mode1(self,
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
                              mode=Throttle.ASYNC_MODE,
                              shutdown_check=shutdown_check_arg)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={float(seconds_arg)}, ' \
            f'mode=Throttle.ASYNC_MODE'

        if shutdown_check_arg:
            expected_repr_str += f', shutdown_check=' \
                                 f'{shutdown_check_arg.__name__}'
        expected_repr_str += ')'
        assert repr(a_throttle) == expected_repr_str

    ###########################################################################
    # repr with mode 2 sync early count
    ###########################################################################
    def test_throttle_repr_mode2(self,
                                 requests_arg: int,
                                 seconds_arg: Union[int, float],
                                 early_count_arg: int,
                                 shutdown_check_arg: Union[None,
                                                           Callable[[], bool]]
                                 ) -> None:
        """test_throttle repr mode 2 with various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args
            early_count_arg: fixture that provides args
            shutdown_check_arg: fixture that provides args
        """
        a_throttle = Throttle(requests=requests_arg,
                              seconds=seconds_arg,
                              mode=Throttle.SYNC_MODE_EC,
                              early_count=early_count_arg,
                              shutdown_check=shutdown_check_arg)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={float(seconds_arg)}, ' \
            f'mode=Throttle.SYNC_MODE_EC), ' \
            f'early_count={early_count_arg}'

        if shutdown_check_arg:
            expected_repr_str += f', shutdown_check=' \
                                 f'{shutdown_check_arg.__name__}'
        expected_repr_str += ')'
        assert repr(a_throttle) == expected_repr_str

    ###########################################################################
    # repr with mode 3 sync leaky bucket
    ###########################################################################
    def test_throttle_repr_mode3(self,
                                 requests_arg: int,
                                 seconds_arg: Union[int, float],
                                 lb_threshold_arg: Union[int, float],
                                 shutdown_check_arg: Union[None,
                                                           Callable[[], bool]]
                                 ) -> None:
        """test_throttle repr with various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args
            lb_threshold_arg: fixture that provides args
            shutdown_check_arg: fixture that provides args
        """
        a_throttle = Throttle(requests=requests_arg,
                              seconds=seconds_arg,
                              mode=Throttle.SYNC_MODE_LB,
                              lb_threshold=lb_threshold_arg,
                              shutdown_check=shutdown_check_arg)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={float(seconds_arg)}, ' \
            f'mode=Throttle.SYNC_MODE_LB), ' \
            f'lb_threshold={float(lb_threshold_arg)}'

        if shutdown_check_arg:
            expected_repr_str += f', shutdown_check=' \
                                 f'{shutdown_check_arg.__name__}'
        expected_repr_str += ')'
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
            @throttle(requests=0, seconds=1, mode=1)
            def f1():
                print('42')
            f1()

        with pytest.raises(IncorrectRequestsSpecified):
            @throttle(requests=-1, seconds=1, mode=1)
            def f1():
                print('42')
            f1()

        with pytest.raises(IncorrectRequestsSpecified):
            @throttle(requests='1', seconds=1, mode=1)  # type: ignore
            def f1():
                print('42')
            f1()
        #######################################################################
        # bad seconds
        #######################################################################
        with pytest.raises(IncorrectSecondsSpecified):
            @throttle(requests=1, seconds=0, mode=1)
            def f1():
                print('42')
            f1()

        with pytest.raises(IncorrectSecondsSpecified):
            @throttle(requests=1, seconds=-1, mode=1)
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectSecondsSpecified):
            @throttle(requests=1, seconds='1', mode=1)  # type: ignore
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
                      mode=4)
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
                      mode=Throttle.ASYNC_MODE,
                      early_count=0)  # not allowed with mode 1
            def f1():
                print('42')
            f1()
        with pytest.raises(MissingEarlyCountSpecification):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.SYNC_MODE_EC)
            def f1():
                print('42')
            f1()
        with pytest.raises(EarlyCountNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.SYNC_MODE_LB,
                      early_count=1)  # not allowed with mode 3
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectEarlyCountSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.SYNC_MODE_EC,
                      early_count=-1)
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectEarlyCountSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.SYNC_MODE_EC,
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
                      mode=Throttle.ASYNC_MODE,
                      lb_threshold=1)  # not allowed with mode 1
            def f1():
                print('42')
            f1()
        with pytest.raises(LbThresholdNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.SYNC_MODE_EC,
                      lb_threshold=0)  # not allowed with mode 2
            def f1():
                print('42')
            f1()
        with pytest.raises(MissingLbThresholdSpecification):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.SYNC_MODE_LB)
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectLbThresholdSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.SYNC_MODE_LB,
                      lb_threshold=-1)
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectLbThresholdSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.SYNC_MODE_LB,
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
                      mode=Throttle.ASYNC_MODE,
                      shutdown_check=1)  # type: ignore
            def f1():
                print('42')
            f1()
        with pytest.raises(IncorrectShutdownCheckSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.ASYNC_MODE,
                      shutdown_check='1')  # type: ignore
            def f1():
                print('42')
            f1()
        with pytest.raises(ShutdownCheckNotAllowed):
            def sd_check() -> bool:
                return True
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.SYNC_MODE_EC,
                      shutdown_check=sd_check)  # type: ignore
            def f1():
                print('42')
            f1()
        with pytest.raises(ShutdownCheckNotAllowed):
            def sd_check() -> bool:
                return True
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.SYNC_MODE_LB,
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
    """Class TestThrottle."""

    ENAB1: Final = 0b00000001

    REQ0_SEC0_ENAB0: Final = 0b00000000
    REQ0_SEC0_ENAB1: Final = 0b00000001
    REQ0_SEC1_ENAB0: Final = 0b00000010
    REQ0_SEC1_ENAB1: Final = 0b00000011
    REQ1_SEC0_ENAB0: Final = 0b00000100
    REQ1_SEC0_ENAB1: Final = 0b00000101
    REQ1_SEC1_ENAB0: Final = 0b00000110
    REQ1_SEC1_ENAB1: Final = 0b00000111

    @staticmethod
    def get_arg_flags(*,
                      requests: int,
                      seconds: Union[int, float],
                      enabled: Union[None, str]
                      ) -> Tuple[int, int, Union[int, float], bool]:
        """Static method get_arg_flags.

        Args:
            requests: None or the number of requests to use
            seconds: None or the number of seconds to use
            enabled: None or the enabled arg to use

        Returns:
              the expected results based on the args
        """
        route_num = TestThrottle.REQ0_SEC0_ENAB0

        expected_requests = 1
        if requests:
            route_num = route_num | TestThrottle.REQ1
            expected_requests = requests

        expected_seconds = 1
        if seconds:
            route_num = route_num | TestThrottle.SEC1
            expected_seconds = seconds

        expected_enabled_tf = True
        if enabled:
            route_num = route_num | TestThrottle.ENAB1
            if (enabled == 'static_false') or (enabled == 'dynamic_false'):
                expected_enabled_tf = False

        return (route_num, expected_requests, expected_seconds,
                expected_enabled_tf)

    """
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
    # test_throttle_mode1
    ###########################################################################
    def test_throttle_mode1(self,
                            capsys: Any,
                            requests_arg: int,
                            seconds_arg: Union[int, float],
                            shutdown_check_arg: Union[None,
                                                      Callable[[], bool]],
                            send_interval_arg: float
                            ) -> None:
        """Method to start throttle mode1 tests

        Args:
            capsys: instance of the capture sysout fixture
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            shutdown_check_arg: function to call to check for shutdown
            send_interval_arg: interval between each send of a request
        """
        self.throttle_router(capsys=capsys,
                             requests=requests_arg,
                             seconds=seconds_arg,
                             mode=1,
                             early_count=None,
                             lb_threshold=None,
                             shutdown_check=shutdown_check_arg,
                             send_interval=send_interval_arg)

    ###########################################################################
    # test_throttle_mode2
    ###########################################################################
    def test_throttle_mode2(self,
                            capsys: Any,
                            requests_arg: int,
                            seconds_arg: Union[int, float],
                            early_count_arg: int,
                            send_interval_arg: float
                            ) -> None:
        """Method to start throttle mode2 tests

        Args:
            capsys: instance of the capture sysout fixture
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            early_count_arg: count used for sync with early count algo
            send_interval_arg: interval between each send of a request
        """
        self.throttle_router(capsys=capsys,
                             requests=requests_arg,
                             seconds=seconds_arg,
                             mode=2,
                             early_count=early_count_arg,
                             lb_threshold=None,
                             shutdown_check=None,
                             send_interval=send_interval_arg)

    ###########################################################################
    # test_throttle_mode3
    ###########################################################################
    def test_throttle_mode3(self,
                            capsys: Any,
                            requests_arg: int,
                            seconds_arg: Union[int, float],
                            lb_threshold_arg: Union[int, float],
                            send_interval_arg: float
                            ) -> None:
        """Method to start throttle mode3 tests

        Args:
            capsys: instance of the capture sysout fixture
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            lb_threshold_arg: threshold used with sync leaky bucket algo
            send_interval_arg: interval between each send of a request
        """
        self.throttle_router(capsys=capsys,
                             requests=requests_arg,
                             seconds=seconds_arg,
                             mode=3,
                             early_count=None,
                             lb_threshold=lb_threshold_arg,
                             shutdown_check=None,
                             send_interval=send_interval_arg)


    ###########################################################################
    # test_throttle_mode1
    ###########################################################################
    def test_pie_throttle_mode1(self,
                                capsys: Any,
                                style_num: int,
                                requests_arg: int,
                                seconds_arg: Union[int, float],
                                shutdown_check_arg: Union[None,
                                                          Callable[[], bool]],
                                enabled_arg: Union[None, str],
                                send_interval_arg: float
                                ) -> None:
        """Method to start throttle mode1 tests

        Args:
            capsys: instance of the capture sysout fixture
            style_num: style from fixture
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            shutdown_check_arg: function to call to check for shutdown
            enabled_arg: specifies whether decorator is enabled
            send_interval_arg: interval between each send of a request
        """
        self.pie_throttle_router(capsys=capsys,
                                 style=style_num,
                                 requests=requests_arg,
                                 seconds=seconds_arg,
                                 mode=1,
                                 early_count=None,
                                 lb_threshold=None,
                                 shutdown_check=shutdown_check_arg,
                                 enabled=enabled_arg,
                                 send_interval=send_interval_arg)

    ###########################################################################
    # test_throttle_mode2
    ###########################################################################
    def test_pie_throttle_mode2(self,
                                capsys: Any,
                                style_num: int,
                                requests_arg: int,
                                seconds_arg: Union[int, float],
                                early_count_arg: int,
                                enabled_arg: Union[None, str],
                                send_interval_arg: float
                                ) -> None:
        """Method to start throttle mode2 tests

        Args:
            capsys: instance of the capture sysout fixture
            style_num: style from fixture
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            early_count_arg: count used for sync with early count algo
            enabled_arg: specifies whether decorator is enabled
            send_interval_arg: interval between each send of a request
        """
        self.pie_throttle_router(capsys=capsys,
                                 style=style_num,
                                 requests=requests_arg,
                                 seconds=seconds_arg,
                                 mode=2,
                                 early_count=early_count_arg,
                                 lb_threshold=None,
                                 shutdown_check=None,
                                 enabled=enabled_arg,
                                 send_interval=send_interval_arg)

    ###########################################################################
    # test_throttle_mode3
    ###########################################################################
    def test_pie_throttle_mode3(self,
                                capsys: Any,
                                style_num: int,
                                requests_arg: int,
                                seconds_arg: Union[int, float],
                                lb_threshold_arg: Union[int, float],
                                enabled_arg: Union[None, str],
                                send_interval_arg: float
                                ) -> None:
        """Method to start throttle mode3 tests

        Args:
            capsys: instance of the capture sysout fixture
            style_num: style from fixture
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            lb_threshold_arg: threshold used with sync leaky bucket algo
            enabled_arg: specifies whether decorator is enabled
            send_interval_arg: interval between each send of a request
        """
        self.pie_throttle_router(capsys=capsys,
                                 style=style_num,
                                 requests=requests_arg,
                                 seconds=seconds_arg,
                                 mode=3,
                                 early_count=None,
                                 lb_threshold=lb_threshold_arg,
                                 shutdown_check=None,
                                 enabled=enabled_arg,
                                 send_interval=send_interval_arg)

    ###########################################################################
    # throttle_decorator_router
    ###########################################################################
    def throttle_router(self,
                        capsys: Any,
                        requests: int,
                        seconds: Union[int, float],
                        mode: int,
                        early_count: Optional[int],
                        lb_threshold: Optional[Union[int, float]],
                        shutdown_check: Union[None, Callable[[], bool]],
                        send_interval: float
                        ) -> None:
        """Method test_throttle_router.

        Args:
            capsys: instance of the capture sysout fixture
            requests: number of requests per interval
            seconds: interval for number of requests
            mode: async or sync_EC or sync_LB
            early_count: count used for sync with early count algo
            lb_threshold: threshold used with sync leaky bucket algo
            shutdown_check: function to call to check for shutdown
            send_interval: interval between each send of a request
        """
        # func: Union[Callable[[int, str], int],
        #              Callable[[int, str], None],
        #              Callable[[], int],
        #              Callable[[], None]]

        a_func: Callable[..., Any]

        expected_return_value: Union[int, None]

        route_num, expected_requests_arg, expected_seconds_arg, enabled_tf \
            = TestThrottle.get_arg_flags(
                      requests=requests_arg,
                      seconds=seconds_arg,
                      enabled=enabled_arg)


        actual_return_value = 0
        
        #######################################################################
        # Instantiate Throttle
        #######################################################################
        if mode == Throttle.ASYNC_MODE:
            if shutdown_check:
                a_throttle = Throttle(requests=requests,
                                      seconds=seconds,
                                      mode=Throttle.ASYNC_MODE,
                                      shutdown_check=shutdown_check
                                      )
            else:
                a_throttle = Throttle(requests=requests,
                                      seconds=seconds,
                                      mode=Throttle.ASYNC_MODE
                                      )
        elif mode  == Throttle.SYNC_MODE_EC:
            a_throttle = Throttle(requests=requests,
                                  seconds=seconds,
                                  mode=Throttle.SYNC_MODE_EC,
                                  early_count=early_count
                                  )
        elif mode == Throttle.SYNC_MODE_LB:
            a_throttle = Throttle(requests=requests,
                                  seconds=seconds,
                                  mode=Throttle.SYNC_MODE_LB,
                                  lb_threshold=lb_threshold
                                  )
        else:
            raise InvalidModeNum('The Mode must be 1,2 or 3')

        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        a_request_validator = RequestValidator(requests=requests,
                                               seconds=seconds,
                                               mode=mode,
                                               early_count=early_count,
                                               lb_threshold=lb_threshold,
                                               send_interval=send_interval)

        #######################################################################
        # Make requests and validate
        #######################################################################
        request_multiplier = 100
        for i in range(requests * request_multiplier):
            # 0
            a_throttle.send_request(a_request_validator.request)
            time.sleep(send_interval)

            # 1
            a_throttle.send_request(a_request_validator.request, i)
            time.sleep(send_interval)

            # 2
            a_throttle.send_request(a_request_validator.request, i, requests)
            time.sleep(send_interval)

            # 3
            a_throttle.send_request(a_request_validator.request, idx=i)
            time.sleep(send_interval)

            # 4
            a_throttle.send_request(a_request_validator.request,
                                    idx=i,
                                    seconds=seconds)
            time.sleep(send_interval)

            # 5
            a_throttle.send_request(a_request_validator.request,
                                    i,
                                    interval=send_interval)
            time.sleep(send_interval)

            # 6
            a_throttle.send_request(a_request_validator.request,
                                    i,
                                    requests,
                                    seconds=seconds,
                                    interval=send_interval)
            time.sleep(send_interval)

        a_request_validator.validate()  # validate and prepare for next batch

    ###########################################################################
    # throttle_decorator_router
    ###########################################################################
    def pie_throttle_router(self,
                            capsys: Any,
                            style: int,
                            requests: int,
                            seconds: Union[int, float],
                            mode: int,
                            early_count: Optional[int],
                            lb_threshold: Optional[Union[int, float]],
                            shutdown_check: Union[None, Callable[[], bool]],
                            enabled: Union[None, str],
                            send_interval: float
                            ) -> None:
        """Method test_throttle_router.

        Args:
            capsys: instance of the capture sysout fixture
            style: style from fixture
            requests: number of requests per interval
            seconds: interval for number of requests
            mode: async or sync_EC or sync_LB
            early_count: count used for sync with early count algo
            lb_threshold: threshold used with sync leaky bucket algo
            shutdown_check: function to call to check for shutdown
            enabled: specifies whether decorator is enabled
            send_interval: interval between each send of a request
        """
        # func: Union[Callable[[int, str], int],
        #              Callable[[int, str], None],
        #              Callable[[], int],
        #              Callable[[], None]]

        a_func: Callable[..., Any]

        expected_return_value: Union[int, None]

        route_num, expected_requests_arg, expected_seconds_arg, enabled_tf \
            = TestThrottle.get_arg_flags(
                      requests=requests_arg,
                      seconds=seconds_arg,
                      enabled=enabled_arg)

        enabled_spec: Union[bool, Callable[..., bool]] = enabled_tf
        def enabled_func() -> bool: return enabled_tf

        if (enabled_arg == 'dynamic_true') or (enabled_arg == 'dynamic_false'):
            enabled_spec = enabled_func
        actual_return_value = 0
        if style_num == 1:
            for func_style in range(1, 5):
                a_func = TestThrottle.build_style1_func(
                    route_num,
                    requests=requests_arg,
                    seconds=seconds_arg,
                    enabled=enabled_spec,
                    f_style=func_style,
                    enabled_tf=enabled_tf
                    )

                if func_style == 1:
                    func_msg = 'The answer is: ' + str(route_num)
                    expected_return_value = route_num * style_num
                    # actual_return_value = a_func(route_num,
                    #                              func_msg)
                    for i in range(requests_arg * 3):
                        actual_return_value = a_func(route_num, func_msg)
                elif func_style == 2:
                    func_msg = 'The answer is: ' + str(route_num)
                    expected_return_value = None
                    # actual_return_value = a_func(route_num, func_msg)
                    for i in range(requests_arg * 3):
                        actual_return_value = a_func(route_num, func_msg)
                elif func_style == 3:
                    func_msg = ''
                    expected_return_value = 42
                    # actual_return_value = a_func()
                    for i in range(requests_arg * 3):
                        actual_return_value = a_func()
                else:  # func_style == 4:
                    func_msg = ''
                    expected_return_value = None
                    # actual_return_value = a_func()
                    for i in range(requests_arg * 3):
                        actual_return_value = a_func()

                TestThrottle.check_results(
                    capsys=capsys,
                    func_msg=func_msg,
                    msg_count=(requests_arg * 3),
                    expected_return_value=expected_return_value,
                    actual_return_value=actual_return_value
                    )
            return

        elif style_num == 2:
            a_func = TestThrottle.build_style2_func(
                route_num,
                requests=requests_arg,
                seconds=seconds_arg,
                enabled=enabled_spec,
                enabled_tf=enabled_tf
                )
        else:  # style_num = 3
            a_func = TestThrottle.build_style3_func(
                route_num,
                requests=requests_arg,
                seconds=seconds_arg,
                enabled=enabled_spec,
                enabled_tf=enabled_tf
                )

        func_msg = 'The answer is: ' + str(route_num)
        expected_return_value = route_num * style_num
        # actual_return_value = a_func(route_num, func_msg)
        for i in range(requests_arg * 3):
            actual_return_value = a_func(route_num, func_msg)
        TestThrottle.check_results(
            capsys=capsys,
            func_msg=func_msg,
            msg_count=(requests_arg * 3),
            expected_return_value=expected_return_value,
            actual_return_value=actual_return_value
            )



    @staticmethod
    def check_results(capsys: Any,
                      func_msg: str,
                      msg_count: int,
                      expected_return_value: Union[int, None],
                      actual_return_value: Union[int, None]
                      ) -> None:
        """Static method check_results.

        Args:
            capsys: instance of the capture sysout fixture
            func_msg: message issued by wrapped function
            expected_return_value: the expected func return value
            actual_return_value: the actual func return value
        """
        actual = capsys.readouterr().out
        if func_msg:
            expected = (func_msg + '\n') * msg_count
        else:
            expected = func_msg

        assert actual == expected

        # check that func returns the correct value

        message = "Expected return value: {0}, Actual return value: {1}"\
            .format(expected_return_value, actual_return_value)
        assert expected_return_value == actual_return_value, message

    @staticmethod
    def build_style1_func(route_num: int,
                          requests: int,
                          seconds: Union[int, float],
                          enabled: Union[bool, Callable[..., bool]],
                          f_style: int,
                          enabled_tf: bool
                          ) -> Callable[..., Any]:
        """Static method build_style1_func.

        Args:
            route_num: specifies how to build the decorator
            requests: number of requests per seconds
            seconds: number of seconds for requests
            enabled: specifies whether the decorator is enabled
            enabled_tf: specifies whether throttle is active
            f_style: type of call to build

        Returns:
              callable decorated function

        Raises:
              InvalidRouteNum: 'route_num was not recognized'
        """
        # func: Union[Callable[[int, str], int],
        #              Callable[[int, str], None],
        #              Callable[[], int],
        #              Callable[[], None]]

        request = Request(requests=requests,
                          seconds=seconds,
                          throttle_TF=enabled_tf)
        if route_num == TestThrottle.REQ1_SEC1_ENAB0:
            if f_style == 1:
                @throttle(requests=requests, seconds=seconds)
                def func(a_int: int, a_str: str) -> int:
                    request.make_request()
                    print(a_str)
                    return a_int * 1
            elif f_style == 2:
                @throttle(requests=requests, seconds=seconds)
                def func(a_int: int, a_str: str) -> None:
                    request.make_request()
                    print(a_str)
            elif f_style == 3:
                @throttle(requests=requests, seconds=seconds)
                def func() -> int:
                    request.make_request()
                    return 42
            else:  # f_style == 4:
                @throttle(requests=requests, seconds=seconds)
                def func() -> None:
                    request.make_request()
        elif route_num == TestThrottle.REQ1_SEC1_ENAB1:
            if f_style == 1:
                @throttle(requests=requests, seconds=seconds,
                          throttle_enabled=enabled)
                def func(a_int: int, a_str: str) -> int:
                    request.make_request()
                    print(a_str)
                    return a_int * 1
            elif f_style == 2:
                @throttle(requests=requests, seconds=seconds,
                          throttle_enabled=enabled)
                def func(a_int: int, a_str: str) -> None:
                    request.make_request()
                    print(a_str)
            elif f_style == 3:
                @throttle(requests=requests, seconds=seconds,
                          throttle_enabled=enabled)
                def func() -> int:
                    request.make_request()
                    return 42
            else:  # f_style == 4:
                @throttle(requests=requests, seconds=seconds,
                          throttle_enabled=enabled)
                def func() -> None:
                    request.make_request()
        else:
            raise InvalidRouteNum('route_num was not recognized')

        return func

    @staticmethod
    def build_style2_func(route_num: int,
                          requests: int,
                          seconds: Union[int, float],
                          enabled: Union[bool, Callable[..., bool]],
                          enabled_tf: bool
                          ) -> Callable[[int, str], int]:
        """Static method build_style2_func.

        Args:
            route_num: specifies how to build the decorator
            requests: number of requests per seconds
            seconds: number of seconds for requests
            enabled: specifies whether the decorator is enabled
            enabled_tf: specifies whether throttle is active

        Returns:
              callable decorated function

        Raises:
              InvalidRouteNum: 'route_num was not recognized'
        """
        request = Request(requests=requests,
                          seconds=seconds,
                          throttle_TF=enabled_tf)
        if route_num == TestThrottle.REQ1_SEC1_ENAB0:
            def func(a_int: int, a_str: str) -> int:
                request.make_request()
                print(a_str)
                return a_int * 2
            func = throttle(func, requests=requests, seconds=seconds)
        elif route_num == TestThrottle.REQ1_SEC1_ENAB1:
            def func(a_int: int, a_str: str) -> int:
                request.make_request()
                print(a_str)
                return a_int * 2
            func = throttle(func, requests=requests, seconds=seconds,
                            throttle_enabled=enabled)
        else:
            raise InvalidRouteNum('route_num was not recognized')

        return func

    @staticmethod
    def build_style3_func(route_num: int,
                          requests: int,
                          seconds: Union[int, float],
                          enabled: Union[bool, Callable[..., bool]],
                          enabled_tf: bool
                          ) -> Callable[[int, str], int]:
        """Static method build_style3_func.

        Args:
            route_num: specifies how to build the decorator
            requests: number of requests per seconds
            seconds: number of seconds for requests
            enabled: specifies whether the decorator is enabled
            enabled_tf: specifies whether throttle is active

        Returns:
              callable decorated function

        Raises:
              InvalidRouteNum: 'route_num was not recognized'
        """
        request = Request(requests=requests,
                          seconds=seconds,
                          throttle_TF=enabled_tf)
        if route_num == TestThrottle.REQ1_SEC1_ENAB0:
            def func(a_int: int, a_str: str) -> int:
                request.make_request()
                print(a_str)
                return a_int * 3
            func = throttle(requests=requests, seconds=seconds)(func)
        elif route_num == TestThrottle.REQ1_SEC1_ENAB1:
            def func(a_int: int, a_str: str) -> int:
                request.make_request()
                print(a_str)
                return a_int * 3
            func = throttle(requests=requests, seconds=seconds,
                            throttle_enabled=enabled)(func)
        else:
            raise InvalidRouteNum('route_num was not recognized')

        return func


###############################################################################
# TestThrottleDocstrings class
###############################################################################
class TestThrottleDocstrings:
    """Class TestThrottleDocstrings."""
    def test_throttle_with_example_1(self) -> None:
        """Method test_throttle_with_example_1."""
        flowers('Example for README:')

        from time import time
        from math import floor
        @throttle(requests=3, seconds=1)
        def make_request(start_i, batch, i, start_time):
            if time() - start_time >= batch:
                print(f'requests {start_i} to {i - 1} during second {batch}')
                return i, batch+1   # update for next batch
            return start_i, batch  # no change

        start_i = 0
        batch = 1
        start_time = time()
        request_times = []
        for i in range(10):
            start_i, batch = make_request(start_i, batch, i, start_time)
            request_times.append(time())
        for i in range(3, 10):
            span = request_times[i]-request_times[i-3]
            print(f'requests {i-3} to {i} made within {span} seconds')


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
