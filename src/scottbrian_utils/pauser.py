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
from typing import Any, Final, Optional, Union

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
# Pauser Class
########################################################################
class Pauser:
    """Pauser class to pause execution."""

    ####################################################################
    # __init__
    ####################################################################
    def __init__(self,
                 min_interval: float = .02,
                 part_time_factor: float = 0.40):
        """Initialize the instance.

        Args:
            min_interval: the minimum interval that will use sleep as
                            part of the pause routine
            part_time_factor: the value to multiply the sleep interval
                                by to reduce the sleep time

        Raise:
            NegativePauseTime: The interval arg is not valid - please
                provide a non-negative value.
        """
        self.min_interval = min_interval
        self.part_time_factor = part_time_factor
        self.total_sleep_time = 0.0

    ####################################################################
    # calibrate
    ####################################################################
    def calibrate(self):
        """Calibrate the pause time."""
        pass

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
            part_time = (stop_time - now_time) * self.part_time_factor
            if part_time >= self.min_interval:
                self.total_sleep_time += part_time  # metrics
                time.sleep(part_time)
            now_time = time.time()
