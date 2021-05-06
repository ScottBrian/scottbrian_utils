"""test_throttle.py module."""

import pytest
# import time
from datetime import datetime, timedelta
from typing import Any, cast, Union
from collections import deque

from scottbrian_utils.throttle import Throttle
from scottbrian_utils.throttle import IncorrectNumberRequestsSpecified
from scottbrian_utils.throttle import IncorrectPerSecondsSpecified

###############################################################################
# num_requests_allowed_arg fixture
###############################################################################
num_requests_allowed_arg_list = [1, 2, 3, 5, 10, 60, 100]


@pytest.fixture(params=num_requests_allowed_arg_list)  # type: ignore
def num_requests_allowed_arg(request: Any) -> int:
    """Using different num_requests_allowed.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# per_seconds_arg fixture
###############################################################################
per_seconds_arg_list = [1, 2, 3, 5, 10, 60]


@pytest.fixture(params=per_seconds_arg_list)  # type: ignore
def per_seconds_arg(request: Any) -> int:
    """Using different per_seconds.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# per_seconds_float_arg fixture
###############################################################################
per_seconds_float_arg_list = [0.1, 0.2, 0.3, 3.3, 10.5, 29.75]


@pytest.fixture(params=per_seconds_float_arg_list)  # type: ignore
def per_seconds_float_arg(request: Any) -> float:
    """Using different per_seconds.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(float, request.param)


class Request:
    """Request class to test throttle."""
    def __init__(self,
                 num_requests_allowed: int,
                 per_seconds: Union[int, float]) -> None:
        """Initialize the request class instance.

        Args:
            num_requests_allowed: number of requests allowed per interval
            per_seconds: interval for number of allowed requests

        """
        self.num_requests_allowed = num_requests_allowed
        self.per_seconds = timedelta(seconds=per_seconds)
        self.request_times = deque()

    def make_request(self) -> None:
        """Make a request."""
        #######################################################################
        # trim queue
        #######################################################################
        self.request_times.append(datetime.utcnow())
        trim_time = self.request_times[-1] - self.per_seconds
        # print('\nrequests before trim:\n', self.request_times)
        while 0 < len(self.request_times):
            if self.request_times[0] < trim_time:
                self.request_times.popleft()
            else:
                break
        # print('\nrequests after trim:\n', self.request_times)
        assert len(self.request_times) <= self.num_requests_allowed


class TestThrottle:
    """TestThrottle class."""
    def test_throttle_bad_args(self) -> None:
        """test_throttle using bad arguments."""
        #######################################################################
        # bad num_requests_allowed
        #######################################################################
        with pytest.raises(IncorrectNumberRequestsSpecified):
            _ = Throttle(num_requests_allowed=0,
                         per_seconds=per_seconds_arg)
        with pytest.raises(IncorrectNumberRequestsSpecified):
            _ = Throttle(num_requests_allowed=-1,
                         per_seconds=per_seconds_arg)
        with pytest.raises(IncorrectNumberRequestsSpecified):
            _ = Throttle(num_requests_allowed='1',  # type: ignore
                         per_seconds=per_seconds_arg)

        #######################################################################
        # bad per_seconds
        #######################################################################
        with pytest.raises(IncorrectPerSecondsSpecified):
            _ = Throttle(num_requests_allowed=1,
                         per_seconds=0)
        with pytest.raises(IncorrectPerSecondsSpecified):
            _ = Throttle(num_requests_allowed=1,
                         per_seconds=-1)
        with pytest.raises(IncorrectPerSecondsSpecified):
            _ = Throttle(num_requests_allowed=1,
                         per_seconds='1')  # type: ignore

    def test_throttle_len(self,
                          num_requests_allowed_arg: int) -> None:
        """Test the len of throttle.

        Args:
            num_requests_allowed_arg: fixture that provides args

        """
        throttle = Throttle(num_requests_allowed=1,
                            per_seconds=1)

        for i in range(num_requests_allowed_arg):
            throttle.after_request()

        assert len(throttle) == num_requests_allowed_arg

    def test_throttle_repr_int(self,
                               num_requests_allowed_arg: int,
                               per_seconds_arg: int
                               ) -> None:
        """test_throttle repr with per_seconds as int.

        Args:
            num_requests_allowed_arg: fixture that provides args
            per_seconds_arg: fixture that provides args

        """
        throttle = Throttle(num_requests_allowed=num_requests_allowed_arg,
                            per_seconds=per_seconds_arg)

        expected_repr_str = \
            f'Throttle(' \
            f'num_requests_allowed={num_requests_allowed_arg}, ' \
            f'per_seconds={timedelta(seconds=per_seconds_arg)})'

        assert repr(throttle) == expected_repr_str

    def test_throttle_repr_float(self,
                                 num_requests_allowed_arg: int,
                                 per_seconds_float_arg: int
                                 ) -> None:
        """test_throttle repr with per_seconds as float.

        Args:
            num_requests_allowed_arg: fixture that provides args
            per_seconds_float_arg: fixture that provides args

        """
        throttle = Throttle(num_requests_allowed=num_requests_allowed_arg,
                            per_seconds=per_seconds_float_arg)

        expected_repr_str = \
            f'Throttle(' \
            f'num_requests_allowed={num_requests_allowed_arg}, ' \
            f'per_seconds={timedelta(seconds=per_seconds_float_arg)})'

        assert repr(throttle) == expected_repr_str

    def test_throttle_int(self,
                          num_requests_allowed_arg: int,
                          per_seconds_arg: int
                          ) -> None:
        """test_throttle using int for seconds.

        Args:
            num_requests_allowed_arg: fixture that provides args
            per_seconds_arg: fixture that provides args
        """
        throttle = Throttle(num_requests_allowed=num_requests_allowed_arg,
                            per_seconds=per_seconds_arg)
        request = Request(num_requests_allowed=num_requests_allowed_arg,
                          per_seconds=per_seconds_arg)
        for i in range(num_requests_allowed_arg*3):
            throttle.before_request()
            request.make_request()
            throttle.after_request()

    def test_throttle_float(self,
                            num_requests_allowed_arg: int,
                            per_seconds_float_arg: int
                            ) -> None:
        """test_throttle using float for seconds.

        Args:
            num_requests_allowed_arg: fixture that provides args
            per_seconds_float_arg: fixture that provides args
        """
        throttle = Throttle(num_requests_allowed=num_requests_allowed_arg,
                            per_seconds=per_seconds_float_arg)
        request = Request(num_requests_allowed=num_requests_allowed_arg,
                          per_seconds=per_seconds_float_arg)
        for i in range(num_requests_allowed_arg * 3):
            throttle.before_request()
            request.make_request()
            throttle.after_request()
