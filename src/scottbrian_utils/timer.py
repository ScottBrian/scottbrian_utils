"""Module timer.

=====
Timer
=====

The Timer class can be used to detect when a process has exceeded a
specified amount of time.

:Example: create a timer and use in a loop

>>> from scottbrian_utils.timer import Timer
>>> import time
>>> print('mainline entered')
>>> timer = Timer(timeout=3)
>>> for idx in range(10):
...   print(f'idx = {idx}')
...   time.sleep(1)
...   if timer.is_expired():
...       print('timer has expired')
...       break
>>> print('mainline exiting')
mainline entered
idx = 0
idx = 1
idx = 2
timer has expired
mainline exiting


The timer module contains:

    1) Timer class with methods:

       a. is_expired

"""

########################################################################
# Standard Library
########################################################################
import time
from typing import Optional, Union

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################


########################################################################
# Timer class exceptions
########################################################################
class TimerError(Exception):
    """Base class for exceptions in this module."""
    pass


########################################################################
# Timer Class
########################################################################
class Timer:
    def __init__(self,
                 timeout: Optional[Union[int, float]] = None,
                 default_timeout: Optional[Union[int, float]] = None) -> None:
        """Initialize a timer object.

        Args:
            timeout: value to use for timeout
            default_timeout: value to use if timeout is None

        """
        self.start_time = time.time()
        # we have either a timeout <= 0 or None which means no timeout
        # can happen, or we have a timeout with a positive value which
        # we will use, or we will use the default timeout which could
        # also be None, in which again means no timeout can happen
        if timeout and timeout <= 0:
            self._timeout = None
        else:
            self._timeout = timeout or default_timeout

    @property
    def timeout(self):
        if self._timeout:  # if not None
            # make sure not negative
            ret_timeout = max(0.0001,
                              self._timeout - (time.time() - self.start_time))
        else:
            ret_timeout = None
        return ret_timeout  # return value of remaining time for timeout

    def is_expired(self) -> bool:
        """Return either True or False for the timer."""
        if self._timeout and self._timeout < (time.time() - self.start_time):
            return True  # we timed out
        else:
            # time remaining, or timeout is None which never expires
            return False
