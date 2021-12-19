"""test_timer.py module."""

########################################################################
# Standard Library
########################################################################
import time
from typing import Any, Optional

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################
from scottbrian_utils.timer import Timer

import logging

logger = logging.getLogger(__name__)


########################################################################
# Timer test exceptions
########################################################################
class ErrorTstTimer(Exception):
    """Base class for exception in this module."""
    pass


###############################################################################
# TestTimerBasic class to test Timer methods
###############################################################################
class TestTimerExamples:
    """Test examples of Timer."""

    ###########################################################################
    # test_timer_example1
    ###########################################################################
    def test_timer_example1(self,
                            capsys: Any) -> None:
        """Test timer example1.

        Args:
            capsys: pytest fixture to capture print output

        """
        # create a timer and use in a loop
        print('mainline entered')
        timer = Timer(timeout=3)
        for idx in range(10):
            print(f'idx = {idx}')
            time.sleep(1)
            if timer.is_expired():
                print('timer has expired')
                break
        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += 'idx = 0\n'
        expected_result += 'idx = 1\n'
        expected_result += 'idx = 2\n'
        expected_result += 'timer has expired\n'
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ###########################################################################
    # test_timer_example2
    ###########################################################################
    def test_timer_example2(self,
                            capsys: Any) -> None:
        """Test timer example2.

        Args:
            capsys: pytest fixture to capture print output

        """
        class A:
            def __init__(self):
                self.a = 1

            def m1(self, sleep_time: float) -> bool:
                timer = Timer(timeout=1)
                time.sleep(sleep_time)
                if timer.is_expired():
                    return False
                return True

        print('mainline entered')
        my_a = A()
        print(my_a.m1(0.5))
        print(my_a.m1(1.5))
        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += 'True\n'
        expected_result += 'False\n'
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ###########################################################################
    # test_timer_example3
    ###########################################################################
    def test_timer_example3(self,
                            capsys: Any) -> None:
        """Test timer example3.

        Args:
            capsys: pytest fixture to capture print output

        """
        class A:
            def __init__(self):
                self.a = 1

            def m1(self, sleep_time: float, timeout: float) -> bool:
                timer = Timer(timeout=timeout)
                time.sleep(sleep_time)
                if timer.is_expired():
                    return False
                return True

        print('mainline entered')
        my_a = A()
        print(my_a.m1(sleep_time=0.5, timeout=0.7))
        print(my_a.m1(sleep_time=1.5, timeout=1.2))
        print(my_a.m1(sleep_time=1.5, timeout=1.8))
        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += 'True\n'
        expected_result += 'False\n'
        expected_result += 'True\n'
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ###########################################################################
    # test_timer_example4
    ###########################################################################
    def test_timer_example4(self,
                            capsys: Any) -> None:
        """Test timer example4.

        Args:
            capsys: pytest fixture to capture print output

        """
        class A:
            def __init__(self, default_timeout: float):
                self.a = 1
                self.default_timeout = default_timeout

            def m1(self,
                   sleep_time: float,
                   timeout: Optional[float] = None) -> bool:
                timer = Timer(timeout=timeout,
                              default_timeout=self.default_timeout)
                time.sleep(sleep_time)
                if timer.is_expired():
                    return False
                return True

        print('mainline entered')
        my_a = A(default_timeout=1.2)
        print(my_a.m1(sleep_time=0.5))
        print(my_a.m1(sleep_time=1.5))
        print(my_a.m1(sleep_time=0.5, timeout=0.3))
        print(my_a.m1(sleep_time=1.5, timeout=1.8))
        print(my_a.m1(sleep_time=1.5, timeout=0))
        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += 'True\n'
        expected_result += 'False\n'
        expected_result += 'False\n'
        expected_result += 'True\n'
        expected_result += 'True\n'
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ###########################################################################
    # test_timer_example5
    ###########################################################################
    def test_timer_example5(self) -> None:
        """Test timer example4."""
        def f1(p1=None):
            print(f'\np1 = {p1}')
            if p1 is not None and p1 > 0:
                print('p1 is greater than zero')
            else:
                print('p1 is NOT greater than zero')
            if p1 and p1 > 0:
                print('p1 is greater than zero')
            else:
                print('p1 is NOT greater than zero')
            if p1:
                print('p1 is something')
            else:
                print('p1 is NOT something')
            if not p1:
                print('p1 is NOT something')
            else:
                print('p1 is something')



        f1(42)
        f1(None)
        f1(0)
        f1(-1)
        f1()



