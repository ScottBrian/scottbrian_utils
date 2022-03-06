"""Module pauser.

======
Pauser
======

The *Pauser* class provides a *pause* method similar to python
``time.sleep()``. ``Pauser.pause()`` uses a ccombination of
``time.sleep()`` and looping on python ``time.perf_counter_ns()`` in an
attempt at being more accurate than using ``time.sleep()`` alone.

:Example: pause execution for 1.5 seconds

>>> from scottbrian_utils.pauser import Pauser
>>> import time
>>> pauser = Pauser()
>>> start_time = time.time()
>>> pauser.pause(1.5)
>>> print(f'paused for {time.time() - start_time:.1f} seconds')
paused for 1.5 seconds

Python ``time.sleep()`` is useful for a rough pause, but at very small
pause intervals it can pause for more time than requested. For example,
``time.sleep(0.001)`` might return 0.015 seconds later in some cases.
``Pauser.pause()`` uses ``time.sleep()`` for a portion of the
pause time, and then finishes the pause using a simple loop while
checking the remaining time with ``time.perf_counter_ns()`` to complete
the requested interval.


The Pauser module contains:

    1) Pauser class with methods:

       a. calibrate
       b. get_metrics
       c. pause

"""

########################################################################
# Standard Library
########################################################################
import time
from typing import Final, NamedTuple, Optional, Type, TYPE_CHECKING, Union

########################################################################
# Third Party
########################################################################

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


class IncorrectInput(PauserError):
    """Input for a method is not correct."""
    pass


########################################################################
# metric_results
########################################################################
class MetricResults(NamedTuple):
    """Results for get_metrics method."""
    pause_ratio: float
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
    CALIBRATION_INCREMENT_MSECS: Final[int] = 5
    CALIBRATION_MAX_INTERVAL_MSECS: Final[int] = 300
    CALIBRATION_ITERATIONS: Final[int] = 8
    CALIBRATION_MAX_LATE_RATIO: Final[float] = 1.0
    MSECS_2_SECS: Final[float] = 0.001
    SECS_2_NS: Final[int] = 1000000000
    NS_2_SECS: Final[float] = 0.000000001

    ####################################################################
    # __init__
    ####################################################################
    def __init__(self,
                 min_interval_secs: float = MIN_INTERVAL_SECS,
                 part_time_factor: float = PART_TIME_FACTOR):
        """Initialize the instance.

        The Pauser instance is initially created with the specified or
        defaulted values for *min_interval_secs* and *part_time_factor*.
        These values should be chosen based on the observed behavior of
        **time.sleep()** at low enough intervals to get an idea of
        where the sleep time fails to reflect the requested sleep time.


        Args:
            min_interval_secs: the minimum interval that will use
                                 ``time.sleep()`` for a portion of the
                                 pause interval.
            part_time_factor: the value to multiply the sleep interval
                                by to reduce the sleep time

        Raises:
            IncorrectInput: The *min_interval_secs* argument is not
                valid - it must be a  positive non-zero float.
            IncorrectInput: The *part_time_factor* argument is not
                valid - it must be a non-zero float no greater than 1.0.

        Example: create an instance of Pauser with defaults

        >>> from scottbrian_utils.pauser import Pauser
        >>> pauser = Pauser()
        >>> pauser
        Pauser(min_interval_secs=0.03, part_time_factor=0.4)

        """
        if min_interval_secs <= 0:
            raise IncorrectInput(
                'The min_interval_secs argument specified as '
                f'{min_interval_secs} is not valid - it must be a '
                'positive non-zero float.')
        if (part_time_factor <= 0.0) or (part_time_factor > 1.0):
            raise IncorrectInput(
                'The part_time_factor argument specified as '
                f'{part_time_factor} is not valid - it must be a '
                'non-zero float no greater than 1.0.')

        self.min_interval_secs = min_interval_secs
        self.part_time_factor = part_time_factor
        self.total_sleep_time = 0.0

    ###########################################################################
    # repr
    ###########################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example: instantiate a Pauser and call repr

        >>> from scottbrian_utils.pauser import Pauser
        >>> pauser = Pauser(min_interval_secs=0.02, part_time_factor=0.3)
        >>> repr(pauser)
        'Pauser(min_interval_secs=0.02, part_time_factor=0.3)'

        """
        if TYPE_CHECKING:
            __class__: Type[Pauser]
        classname = self.__class__.__name__
        parms = (f'min_interval_secs={self.min_interval_secs}, '
                 f'part_time_factor={self.part_time_factor}')

        return f'{classname}({parms})'

    ####################################################################
    # calibrate
    ####################################################################
    def calibrate(self,
                  min_interval_msecs: int = CALIBRATION_MIN_INTERVAL_MSECS,
                  max_interval_msecs: int = CALIBRATION_MAX_INTERVAL_MSECS,
                  increment: int = CALIBRATION_INCREMENT_MSECS,
                  part_time_factor: float = CALIBRATION_PART_TIME_FACTOR,
                  max_sleep_late_ratio: float = CALIBRATION_MAX_LATE_RATIO,
                  iterations: int = CALIBRATION_ITERATIONS) -> None:
        """Calibrate the pause time.

        Args:
            min_interval_msecs: starting interval of span to calibrate
            max_interval_msecs: ending interval of span to calibrate
            increment: number of milliseconds to skip for the next
                         interval
            part_time_factor: factor of sleep time to try
            max_sleep_late_ratio: allowed error threshold
            iterations: number of iteration per interval

        Raises:
            IncorrectInput: The *min_interval_msecs* argument is not
                valid - it must be a positive non-zero integer.
            IncorrectInput: The *max_interval_msecs* argument is not
                valid - it must be a positive non-zero integer
                equal to or greater than min_interval_msecs.
            IncorrectInput: The *increment argument* is not valid - it
                must be a positive non-zero integer.
            IncorrectInput: The *part_time_factor* argument is not
                valid - it must be a positive non-zero float no greater
                than 1.0.
            IncorrectInput: The *max_sleep_late_ratio* argument is not
                valid - it must be a positive non-zero float no greater
                than 1.0.
            IncorrectInput: The *iterations* argument is not valid - it
                must be a positive non-zero integer.
        """
        if ((not isinstance(min_interval_msecs, int))
                or (min_interval_msecs <= 0)):
            raise IncorrectInput(
                'The min_interval_msecs argument specified as '
                f'{min_interval_msecs} is not valid - it must be a '
                f'positive non-zero integer.')

        if ((not isinstance(max_interval_msecs, int))
                or (max_interval_msecs < min_interval_msecs)):
            raise IncorrectInput(
                'The max_interval_msecs argument specified as '
                f'{max_interval_msecs} is not valid - it must be a '
                'positive non-zero integer equal to or greater than '
                'min_interval_msecs.')

        if ((not isinstance(increment, int))
                or (increment <= 0)):
            raise IncorrectInput(
                'The increment argument specified as '
                f'{increment} is not valid - it must be a positive '
                'non-zero integer.')

        if (part_time_factor <= 0.0) or (part_time_factor > 1.0):
            raise IncorrectInput(
                'The part_time_factor argument specified as '
                f'{part_time_factor} is not valid - it must be a '
                'positive non-zero float no greater than 1.0.')

        if (max_sleep_late_ratio <= 0.0) or (max_sleep_late_ratio > 1.0):
            raise IncorrectInput(
                'The max_sleep_late_ratio argument specified as '
                f'{max_sleep_late_ratio} is not valid - it must be a '
                'positive non-zero float no greater than 1.0.')

        if (not isinstance(iterations, int)) or (iterations <= 0):
            raise IncorrectInput(
                'The iterations argument specified as '
                f'{iterations} is not valid - it must be a positive '
                'non-zero integer.')

        min_interval_secs = min_interval_msecs * Pauser.MSECS_2_SECS
        for interval_msecs in range(min_interval_msecs,
                                    max_interval_msecs+1,
                                    increment):
            interval_secs = interval_msecs * Pauser.MSECS_2_SECS
            sleep_time = interval_secs * part_time_factor
            for _ in range(iterations):
                start_time = time.perf_counter_ns()
                time.sleep(sleep_time)
                stop_time = time.perf_counter_ns()
                interval_time = (stop_time - start_time) * Pauser.NS_2_SECS
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
                    iterations: int = CALIBRATION_ITERATIONS
                    ) -> MetricResults:
        """Get the pauser metrics.

        Args:
            min_interval_msecs: starting number of milliseconds for scan
            max_interval_msecs: ending number of milliseconds for scan
            iterations: number of iterations to run each interval

        Returns:
            The pause interval ratio (actual/requested) and the sleep
              ratio (sleep/requested)

        Raises:
            IncorrectInput: The *min_interval_msecs* argument is not
                valid - it must be a positive non-zero integer.
            IncorrectInput: The *max_interval_msecs* argument is not
                valid - it must be a positive  non-zero integer equal to
                or greater than min_interval_msecs.
            IncorrectInput: The *iterations* argument is not valid - it
                must be a positive non-zero integer.
        """
        if ((not isinstance(min_interval_msecs, int))
                or (min_interval_msecs <= 0)):
            raise IncorrectInput(
                'The min_interval_msecs argument specified as '
                f'{min_interval_msecs} is not valid - it must be a '
                'positive non-zero integer.')

        if ((not isinstance(max_interval_msecs, int))
                or (max_interval_msecs < min_interval_msecs)):
            raise IncorrectInput(
                'The max_interval_msecs argument specified as '
                f'{max_interval_msecs} is not valid - it must be a '
                'positive  non-zero integer equal to or greater than '
                'min_interval_msecs.')

        if (not isinstance(iterations, int)) or (iterations <= 0):
            raise IncorrectInput(
                'The iterations argument specified as '
                f'{iterations} is not valid - it must be a positive '
                'non-zero integer.')

        metric_pauser = Pauser(min_interval_secs=self.min_interval_secs,
                               part_time_factor=self.part_time_factor)
        metric_pauser.total_sleep_time = 0.0
        total_requested_pause_time = 0.0
        total_actual_pause_time = 0.0
        for interval_msecs in range(min_interval_msecs,
                                    max_interval_msecs+1):
            pause_time = interval_msecs * Pauser.MSECS_2_SECS

            for _ in range(iterations):
                total_requested_pause_time += pause_time
                start_time = time.perf_counter_ns()
                metric_pauser.pause(pause_time)
                stop_time = time.perf_counter_ns()
                total_actual_pause_time += ((stop_time - start_time)
                                            * Pauser.NS_2_SECS)

        pause_ratio = (total_actual_pause_time
                       / total_requested_pause_time)
        sleep_ratio = (metric_pauser.total_sleep_time
                       / total_requested_pause_time)

        return MetricResults(pause_ratio=pause_ratio,
                             sleep_ratio=sleep_ratio)

    ####################################################################
    # pause
    ####################################################################
    def pause(self, interval: IntFloat) -> None:
        """Pause for the specified number of seconds.

        Args:
            interval: number of seconds to pause

        Raises:
            IncorrectInput: The interval arg is not valid - please
                provide a non-negative value.
        """
        now_time = time.perf_counter_ns()  # start the timing
        if interval < 0:
            raise IncorrectInput(
                f'The interval arg of {interval} is not valid - '
                f'please provide a non-negative value.')

        stop_time = now_time + (interval * Pauser.SECS_2_NS)
        while now_time < stop_time:
            remaining_time = (stop_time - now_time) * Pauser.NS_2_SECS
            if self.min_interval_secs < remaining_time:
                part_time = remaining_time * self.part_time_factor
                self.total_sleep_time += part_time  # metrics
                time.sleep(part_time)
            now_time = time.perf_counter_ns()
