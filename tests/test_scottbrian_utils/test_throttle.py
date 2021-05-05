"""test_throttle.py module."""

import pytest
import time
from datetime import datetime, timedelta
from typing import Any, cast, List
from collections import deque

from scottbrian_utils.throttle import Throttle


class Request:
    """Request class to test throttle."""
    def __init__(self, num_requests_allowed, per_seconds) -> None:
        """Initialize the request class instance.

        Args:
            num_requests: number of requests allowed per interval
            per_second: interval for number of allowed requests

        """
        self.num_requests_allowed = num_requests_allowed
        self.per_seconds = timedelta(seconds=per_seconds)
        self.request_times = deque()

    def make(self) -> None:
        """Make a request."""
        #######################################################################
        # trim queue
        #######################################################################
        self.request_times.append(datetime.utcnow())
        trim_time = self.request_times[-1] - self.per_seconds
        print('\nrequests before trim:\n', self.request_times)
        for item in self.request_times:
            if item < trim_time:
                self.request_times.popleft()
        print('\nrequests after trim:\n', self.request_times)
        assert len(self.request_times) < self.num_requests_allowed


class TestThrottle:
    """TestThrottle class."""
    def test_throttle(self) -> None:
        """test_throttle method."""
        for num_request_allowed in range(1, 10):
            for per_seconds in range(1, 10):
                throttle = Throttle(num_requests_allowed=num_request_allowed,
                                    per_seconds=per_seconds)
                request = Request(num_requests_allowed=num_request_allowed,
                                  per_seconds=per_seconds)
                for i in range(10):
                    throttle.before_request()
                    time.sleep(1.1)
                    request.make()
                    time.sleep(1.1)
                    throttle.after_request()

        for num_request_allowed in range(1, 10):
            for per_seconds in (0.1, 0.2, 0.5, 1.5, 3.3):
                throttle = Throttle(num_requests_allowed=num_request_allowed,
                                    per_seconds=per_seconds)
                request = Request(num_requests_allowed=num_request_allowed,
                                  per_seconds=per_seconds)
                for i in range(10):
                    throttle.before_request()
                    time.sleep(1.1)
                    request.make()
                    time.sleep(1.1)
                    throttle.after_request()
