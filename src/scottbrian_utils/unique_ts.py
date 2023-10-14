"""Module unique_ts.

========
UniqueTS
========

The UniqueTS class can be used to obtain a unique time stamp.

.. image:: UniqueTS_UseCase1.svg

:Example1: obtain non-unique time stamps

This example shows that obtaining two time stamps in quick
        succession does not guarantee they will be unique.

>>> import time
>>> first_time_stamp = time.time()
>>> second_time_stamp = time.time()
>>> print(second_time_stamp > first_time_stamp)
False


:Example2: obtain non-unique time stamps

This example shows that obtaining two time stamps in quick
        succession with the first from time.time() and the second
        using get_unique_time_ts() does not guarantee they will be
        unique.

>>> from scottbrian_utils.unique_ts import UniqueTS, UniqueTStamp
>>> first_time_stamp = time.time()
>>> second_time_stamp: UniqueTStamp = UniqueTS.get_unique_ts()
>>> print(second_time_stamp > first_time_stamp)
False


:Example3: obtain unique time stamps

This example shows that obtaining two time stamps in quick
        succession using get_unique_time_ts() guarantees they will be
        unique.

>>> from scottbrian_utils.unique_ts import UniqueTS, UniqueTStamp
>>> first_time_stamp: UniqueTStamp = UniqueTS.get_unique_ts()
>>> second_time_stamp: UniqueTStamp = UniqueTS.get_unique_ts()
>>> print(second_time_stamp > first_time_stamp)
True


"""

########################################################################
# Standard Library
########################################################################
from threading import Lock
import time
from typing import cast, ClassVar, NewType

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################

########################################################################
# type aliases
########################################################################
UniqueTStamp = NewType("UniqueTStamp", float)


########################################################################
# UniqueTS Class
########################################################################
class UniqueTS:
    """Unique Time Stamp class."""

    ####################################################################
    # Class Vars
    ####################################################################
    _unique_ts: ClassVar[UniqueTStamp] = cast(UniqueTStamp, 0.0)
    _unique_ts_lock: ClassVar[Lock] = Lock()

    @classmethod
    def get_unique_ts(cls) -> UniqueTStamp:
        """Return a unique time stamp.

        Returns:
            a unique time stamp
        """
        with cls._unique_ts_lock:
            ret_ts: UniqueTStamp = cls._unique_ts
            while ret_ts == cls._unique_ts:
                ret_ts = cast(UniqueTStamp, time.time())
            cls._unique_ts = ret_ts

        return ret_ts
