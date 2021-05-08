"""test_throttle.py module."""

import pytest
from time import time
from datetime import datetime, timedelta
from typing import Any, Callable, cast, Final, Tuple, Union
from collections import deque

from scottbrian_utils.flower_box import print_flower_box_msg as flowers

from scottbrian_utils.throttle import Throttle, throttle
from scottbrian_utils.throttle import IncorrectNumberRequestsSpecified
from scottbrian_utils.throttle import IncorrectPerSecondsSpecified


###############################################################################
# Throttle test exceptions
###############################################################################
class ErrorTstThrottle(Exception):
    """Base class for exception in this module."""
    pass


class InvalidRouteNum(ErrorTstThrottle):
    """InvalidRouteNum exception class."""
    pass


###############################################################################
# requests_arg fixture
###############################################################################
requests_arg_list = [1, 2, 3, 5, 10, 60, 100]


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
seconds_arg_list = [0.1, 0.2, 0.3, 1, 2, 3, 3.3, 5, 10, 10.5, 29.75, 60]


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
# Request class use to verify tests
###############################################################################
class Request:
    """Request class to test throttle."""
    def __init__(self,
                 requests: int,
                 seconds: Union[int, float]) -> None:
        """Initialize the request class instance.

        Args:
            requests: number of requests allowed per interval
            seconds: interval for number of allowed requests

        """
        self.requests = requests
        self.seconds = timedelta(seconds=seconds)
        self.request_times = deque()

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
        assert len(self.request_times) <= self.requests


###############################################################################
# TestThrottleBasic class to test Throttle methods
###############################################################################
class TestThrottleBasic:
    """TestThrottle class."""
    def test_throttle_bad_args(self) -> None:
        """test_throttle using bad arguments."""
        #######################################################################
        # bad requests
        #######################################################################
        with pytest.raises(IncorrectNumberRequestsSpecified):
            _ = Throttle(requests=0,
                         seconds=1)
        with pytest.raises(IncorrectNumberRequestsSpecified):
            _ = Throttle(requests=-1,
                         seconds=1)
        with pytest.raises(IncorrectNumberRequestsSpecified):
            _ = Throttle(requests='1',  # type: ignore
                         seconds=1)

        #######################################################################
        # bad seconds
        #######################################################################
        with pytest.raises(IncorrectPerSecondsSpecified):
            _ = Throttle(requests=1,
                         seconds=0)
        with pytest.raises(IncorrectPerSecondsSpecified):
            _ = Throttle(requests=1,
                         seconds=-1)
        with pytest.raises(IncorrectPerSecondsSpecified):
            _ = Throttle(requests=1,
                         seconds='1')  # type: ignore

    def test_throttle_len(self,
                          requests_arg: int) -> None:
        """Test the len of throttle.

        Args:
            requests_arg: fixture that provides args

        """
        throttle = Throttle(requests=1,
                            seconds=1)

        for i in range(requests_arg):
            throttle.after_request()

        assert len(throttle) == requests_arg

    def test_throttle_repr(self,
                           requests_arg: int,
                           seconds_arg: Union[int, float]
                           ) -> None:
        """test_throttle repr with various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args

        """
        throttle = Throttle(requests=requests_arg,
                            seconds=seconds_arg)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={timedelta(seconds=seconds_arg)})'

        assert repr(throttle) == expected_repr_str

    def test_throttle_basic(self,
                            requests_arg: int,
                            seconds_arg: Union[int, float]
                            ) -> None:
        """test_throttle using various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args
        """
        throttle = Throttle(requests=requests_arg,
                            seconds=seconds_arg)
        request = Request(requests=requests_arg,
                          seconds=seconds_arg)
        for i in range(requests_arg*3):
            throttle.before_request()
            request.make_request()
            throttle.after_request()


###############################################################################
# TestThrottleBasicDecorator class
###############################################################################
class TestThrottleBasicDecorator:
    """TestThrottleDecorator class."""
    def test_pie_throttle_bad_args(self) -> None:
        """test_throttle using bad arguments."""
        #######################################################################
        # bad requests
        #######################################################################
        with pytest.raises(IncorrectNumberRequestsSpecified):
            @throttle(requests=0, seconds=1)
            def f1() -> int:
                return 42

        with pytest.raises(IncorrectNumberRequestsSpecified):
            @throttle(requests=-1, seconds=1)
            def f2() -> int:
                return 42

        with pytest.raises(IncorrectNumberRequestsSpecified):
            @throttle(requests='1', seconds=1)
            def f3() -> int:
                return 42

        #######################################################################
        # bad seconds
        #######################################################################
        with pytest.raises(IncorrectPerSecondsSpecified):
            @throttle(requests=1, seconds=0)
            def f1() -> int:
                return 42

        with pytest.raises(IncorrectPerSecondsSpecified):
            @throttle(requests=1, seconds=-1)
            def f2() -> int:
                return 42

        with pytest.raises(IncorrectPerSecondsSpecified):
            @throttle(requests=1, seconds='1')
            def f3() -> int:
                return 42

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
            # print('\nrequests before trim:\n', self.request_times)
            while 0 < len(a_request_times):
                if a_request_times[0] < trim_time:
                    a_request_times.popleft()
                else:
                    break
            # print('\nrequests after trim:\n', self.request_times)
            assert len(a_request_times) <= a_requests

        for i in range(requests_arg*3):
            make_request()


###############################################################################
# TestThrottleDocstrings class
###############################################################################
class TestThrottleDocstrings:
    """Class TestThrottleDocstrings."""
    def test_throttle_with_example_1(self) -> None:
        """Method test_throttle_with_example_1."""
        flowers('Example for README:')

        @throttle(requests=10, seconds=1)
        def make_request(start_i, batch, i, start_time):
            if time() - start_time >= batch:
                print(f'requests {start_i} to {i - 1} during second {batch}')
                return i, batch+1   # update for next batch
            return start_i, batch  # no change

        start_i = 0
        batch = 1
        start_time = time()
        for i in range(30):
            start_i, batch = make_request(start_i, batch, i, start_time)

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


###############################################################################
# TestThrottle class
###############################################################################
class TestThrottle:
    """Class TestThrottle."""
    REQ1: Final = 0b00000100
    SEC1: Final = 0b00000010
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
    The following section tests each combination of arguments to the throttle
    decorator for three styles of decoration (using pie, calling
    with the function as the first parameter, and calling the decorator with
    the function specified after the call. This test is especially useful to
    ensure that the type hints are working correctly, and that all
    combinations are accepted by python.

    The following keywords with various values and in all combinations are
    tested:
        requests - various increments 
        seconds - various increments, both int and float
        throttle_enabled - true/false

    """

    def test_throttle_router(self,
                             capsys: Any,
                             style_num: int,
                             requests_arg: int,
                             seconds_arg: Union[int, float],
                             enabled_arg: Union[None, str]
                             ) -> None:
        """Method test_throttle_router.

        Args:
            capsys: instance of the capture sysout fixture
            style_num: style from fixture
            requests_arg: number of requests per interval
            seconds_arg: interval for number of requests
            enabled_arg: specifies whether decorator is enabled
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

        if style_num == 1:
            for func_style in range(1, 5):
                a_func = TestThrottle.build_style1_func(
                    route_num,
                    requests=requests_arg,
                    seconds=seconds_arg,
                    enabled=enabled_spec,
                    f_style=func_style
                    )

                if func_style == 1:
                    func_msg = 'The answer is: ' + str(route_num)
                    expected_return_value = route_num * style_num
                    actual_return_value = a_func(route_num,
                                                 func_msg)
                elif func_style == 2:
                    func_msg = 'The answer is: ' + str(route_num)
                    expected_return_value = None
                    actual_return_value = a_func(route_num, func_msg)
                elif func_style == 3:
                    func_msg = ''
                    expected_return_value = 42
                    actual_return_value = a_func()
                else:  # func_style == 4:
                    func_msg = ''
                    expected_return_value = None
                    actual_return_value = a_func()

                TestThrottle.check_results(
                    capsys=capsys,
                    func_msg=func_msg,
                    expected_return_value=expected_return_value,
                    actual_return_value=actual_return_value
                    )
                # if route_num > TestThrottle.DT0_END0_FILE1_FLUSH1_ENAB1:
                #     break
            return

        elif style_num == 2:
            a_func = TestThrottle.build_style2_func(
                route_num,
                requests=requests_arg,
                seconds=seconds_arg,
                enabled=enabled_spec
                )
        else:  # style_num = 3
            a_func = TestThrottle.build_style3_func(
                route_num,
                requests=requests_arg,
                seconds=seconds_arg,
                enabled=enabled_spec
                )

        func_msg = 'The answer is: ' + str(route_num)
        expected_return_value = route_num * style_num
        actual_return_value = a_func(route_num, func_msg)
        TestThrottle.check_results(
            capsys=capsys,
            func_msg=func_msg,
            expected_return_value=expected_return_value,
            actual_return_value=actual_return_value
            )

    @staticmethod
    def check_results(capsys: Any,
                      func_msg: str,
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
        expected = func_msg + '\n'
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
                          f_style: int
                          ) -> Callable[..., Any]:
        """Static method build_style1_func.

        Args:
            route_num: specifies how to build the decorator
            requests: number of requests per seconds
            seconds: number of seconds for requests
            enabled: specifies whether the decorator is enabled
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

        if route_num == TestThrottle.REQ1_SEC1_ENAB0:
            if f_style == 1:
                @throttle(requests=requests, seconds=seconds)
                def func(a_int: int, a_str: str) -> int:
                    request = Request(requests=requests,
                                      seconds=seconds)
                    for i in range(requests * 3):
                        request.make_request()
                    print(a_str)
                    return a_int * 1
            elif f_style == 2:
                @throttle(requests=requests, seconds=seconds)
                def func(a_int: int, a_str: str) -> None:
                    request = Request(requests=requests,
                                      seconds=seconds)
                    for i in range(requests * 3):
                        request.make_request()
                    print(a_str)
            elif f_style == 3:
                @throttle(requests=requests, seconds=seconds)
                def func() -> int:
                    request = Request(requests=requests,
                                      seconds=seconds)
                    for i in range(requests * 3):
                        request.make_request()
                    return 42
            else:  # f_style == 4:
                @throttle(requests=requests, seconds=seconds)
                def func() -> None:
                    request = Request(requests=requests,
                                      seconds=seconds)
                    for i in range(requests * 3):
                        request.make_request()
        elif route_num == TestThrottle.REQ1_SEC1_ENAB1:
            if f_style == 1:
                @throttle(requests=requests, seconds=seconds,
                          throttle_enabled=enabled)
                def func(a_int: int, a_str: str) -> int:
                    request = Request(requests=requests,
                                      seconds=seconds)
                    for i in range(requests * 3):
                        request.make_request()
                    print(a_str)
                    return a_int * 1
            elif f_style == 2:
                @throttle(requests=requests, seconds=seconds,
                          throttle_enabled=enabled)
                def func(a_int: int, a_str: str) -> None:
                    request = Request(requests=requests,
                                      seconds=seconds)
                    for i in range(requests * 3):
                        request.make_request()
                    print(a_str)
            elif f_style == 3:
                @throttle(requests=requests, seconds=seconds,
                          throttle_enabled=enabled)
                def func() -> int:
                    request = Request(requests=requests,
                                      seconds=seconds)
                    for i in range(requests * 3):
                        request.make_request()
                    return 42
            else:  # f_style == 4:
                @throttle(requests=requests, seconds=seconds,
                          throttle_enabled=enabled)
                def func() -> None:
                    request = Request(requests=requests,
                                      seconds=seconds)
                    for i in range(requests * 3):
                        request.make_request()
        else:
            raise InvalidRouteNum('route_num was not recognized')

        return func

    @staticmethod
    def build_style2_func(route_num: int,
                          requests: int,
                          seconds: Union[int, float],
                          enabled: Union[bool, Callable[..., bool]]
                          ) -> Callable[[int, str], int]:
        """Static method build_style2_func.

        Args:
            route_num: specifies how to build the decorator
            requests: number of requests per seconds
            seconds: number of seconds for requests
            enabled: specifies whether the decorator is enabled

        Returns:
              callable decorated function

        Raises:
              InvalidRouteNum: 'route_num was not recognized'
        """
        if route_num == TestThrottle.REQ1_SEC1_ENAB0:
            def func(a_int: int, a_str: str) -> int:
                request = Request(requests=requests,
                                  seconds=seconds)
                for i in range(requests * 3):
                    request.make_request()
                print(a_str)
                return a_int * 2
            func = throttle(func, requests=requests, seconds=seconds)
        elif route_num == TestThrottle.REQ1_SEC1_ENAB1:
            def func(a_int: int, a_str: str) -> int:
                request = Request(requests=requests,
                                  seconds=seconds)
                for i in range(requests * 3):
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
                          enabled: Union[bool, Callable[..., bool]]
                          ) -> Callable[[int, str], int]:
        """Static method build_style3_func.

        Args:
            route_num: specifies how to build the decorator
            requests: number of requests per seconds
            seconds: number of seconds for requests
            enabled: specifies whether the decorator is enabled

        Returns:
              callable decorated function

        Raises:
              InvalidRouteNum: 'route_num was not recognized'
        """
        if route_num == TestThrottle.REQ1_SEC1_ENAB0:
            def func(a_int: int, a_str: str) -> int:
                request = Request(requests=requests,
                                  seconds=seconds)
                for i in range(requests * 3):
                    request.make_request()
                print(a_str)
                return a_int * 3
            func = throttle(requests=requests, seconds=seconds)(func)
        elif route_num == TestThrottle.REQ1_SEC1_ENAB1:
            def func(a_int: int, a_str: str) -> int:
                request = Request(requests=requests,
                                  seconds=seconds)
                for i in range(requests * 3):
                    request.make_request()
                print(a_str)
                return a_int * 3
            func = throttle(requests=requests, seconds=seconds,
                            throttle_enabled=enabled)(func)
        else:
            raise InvalidRouteNum('route_num was not recognized')

        return func
