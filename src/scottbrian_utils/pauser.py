"""Module pauser.

======
Pauser
======

The *Pauser* class provides a *pause* function similar to the python
*sleep* function that is intended to be more accurate.

:Example: pause execution for 1.5 seconds

>>> from scottbrian_utils.pauser import Pauser
>>> import time
>>> pauser = Pauser()
>>> start_time = time.time()
>>> pauser.pause(1.5)
>>> print(f'paused for {time.time() - start_time:.1f} seconds')
paused for 1.5 seconds

The python sleep function is useful for a rough pause, but at very small
pause intervals it can pause for more time than requested. For example,
sleep(0.001) can pause for 0.015 seconds in some cases. The *pause*
function of *Pauser* uses the *sleep* function for a portion of the
pause time, and then finishes the pause using a simple loop while
checking the time against the stop time to complete the request pause
interval.


The Pauser module contains:

    1) Pauser class with methods:

       a. pause

"""

########################################################################
# Standard Library
########################################################################
import logging
import queue
import threading
import time
from typing import Any, Final, NamedTuple, Optional, Union

########################################################################
# Third Party
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.timer import Timer

########################################################################
# Local
########################################################################

########################################################################
# type aliases
########################################################################
IntFloat = Union[int, float]
OptIntFloat = Optional[IntFloat]


########################################################################
# Msg Exceptions classes
########################################################################
class PauserError(Exception):
    """Base class for exception in this module."""
    pass


class NegativePauseTime(PauserError):
    """Pauser pause method time arg is negative."""
    pass


########################################################################
# metric_results
########################################################################
class MetricResults(NamedTuple):
    actual_pause_ratio: float
    sleep_ratio: float


########################################################################
# Pauser Class
########################################################################
class Pauser:
    """Pauser class to pause execution."""

    MIN_INTERVAL_SECS: Final[float] = 0.03
    PART_TIME_FACTOR: Final[float] = 0.4
    CALIBRATION_PART_TIME_FACTOR: Final[float] = 0.4
    CALIBRATION_MIN_INTERVAL_MSECS: Final[int] = 1
    CALIBRATION_MAX_INTERVAL_MSECS: Final[int] = 400
    CALIBRATION_ITERATIONS: Final[int] = 16
    CALIBRATION_MAX_LATE_RATIO: Final[float] = 1.0
    MSECS_2_SECS: Final[float] = 0.001

    ####################################################################
    # __init__
    ####################################################################
    def __init__(self,
                 min_interval_secs: float = MIN_INTERVAL_SECS,
                 part_time_factor: float = PART_TIME_FACTOR):
        """Initialize the instance.

        Args:
            min_interval_secs: the minimum interval that will use sleep
                                 as part of the pause routine
            part_time_factor: the value to multiply the sleep interval
                                by to reduce the sleep time

        Raise:
            NegativePauseTime: The interval arg is not valid - please
                provide a non-negative value.
        """
        self.min_interval_secs = min_interval_secs
        self.part_time_factor = part_time_factor
        self.total_sleep_time = 0.0

    ####################################################################
    # calibrate
    ####################################################################
    def calibrate(self,
                  min_interval_msecs: int = CALIBRATION_MIN_INTERVAL_MSECS,
                  max_interval_msecs: int = CALIBRATION_MAX_INTERVAL_MSECS,
                  part_time_factor: float = CALIBRATION_PART_TIME_FACTOR,
                  max_sleep_late_ratio: float = CALIBRATION_MAX_LATE_RATIO,
                  iterations: int = CALIBRATION_ITERATIONS) -> None:
        """Calibrate the pause time.

        Args:
            min_interval_msecs: starting interval in span
            max_interval_msecs: ending interval in span
            part_time_factor: factor of sleep time to try
            max_sleep_late_ratio: allowed error threshold
            iterations: number of iteration per interval
        """
        min_interval_secs = min_interval_msecs * Pauser.MSECS_2_SECS
        for interval_msecs in range(min_interval_msecs, max_interval_msecs+1):
            interval_secs = interval_msecs * Pauser.MSECS_2_SECS
            sleep_time = interval_secs * part_time_factor
            for _ in range(iterations):
                start_time = time.time()
                time.sleep(sleep_time)
                stop_time = time.time()
                interval_time = stop_time - start_time
                if max_sleep_late_ratio < (interval_time/interval_secs):
                    min_interval_secs = interval_secs
                    break
        self.min_interval_secs = min_interval_secs
        self.part_time_factor = part_time_factor

    ####################################################################
    # get_metrics
    ####################################################################
    def get_metrics(self,
                    min_interval_msecs: int = CALIBRATION_MIN_INTERVAL_MSECS,
                    max_interval_msecs: int = CALIBRATION_MAX_INTERVAL_MSECS,
                    num_iterations: int = CALIBRATION_ITERATIONS
                    ) -> MetricResults:
        """Get the pauser metrics.

        Args:
            min_interval_msecs: starting number of milliseconds for scan
            max_interval_msecs: ending number of milliseconds for scan
            num_iterations: number of iterations to run each interval

        Returns:
            The pause interval ratio (actual/requested) and the sleep
              ratio (sleep/requested)

        """
        metric_pauser = Pauser(min_interval_secs=self.min_interval_secs,
                               part_time_factor=self.part_time_factor)
        metric_pauser.total_sleep_time = 0.0
        total_requested_pause_time = 0.0
        total_actual_pause_time = 0.0
        for interval_msecs in range(min_interval_msecs,
                                    max_interval_msecs):
            pause_time = interval_msecs * Pauser.MSECS_2_SECS

            for _ in range(num_iterations):
                total_requested_pause_time += pause_time
                start_time = time.time()
                metric_pauser.pause(pause_time)
                stop_time = time.time()
                total_actual_pause_time += (stop_time - start_time)

        actual_pause_ratio = (total_actual_pause_time
                              / total_requested_pause_time)
        sleep_ratio = (metric_pauser.total_sleep_time
                       / total_requested_pause_time)

        return MetricResults(actual_pause_ratio=actual_pause_ratio,
                             sleep_ratio=sleep_ratio)

    ####################################################################
    # pause
    ####################################################################
    def pause(self, interval: IntFloat):
        """Pause for the specified number of seconds.

        Args:
            interval: number of seconds to pause
        """
        now_time = time.time()  # start the timing
        if interval < 0:
            raise NegativePauseTime(
                f'The interval arg of {interval} is not valid - '
                f'please provide a non-negative value.')

        stop_time = now_time + interval
        while now_time < stop_time:
            remaining_time = stop_time - now_time
            if self.min_interval_secs < remaining_time:
                part_time = remaining_time * self.part_time_factor
                self.total_sleep_time += part_time  # metrics
                time.sleep(part_time)
            now_time = time.time()
