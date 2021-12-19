"""test_timer.py module."""

########################################################################
# Standard Library
########################################################################
import logging
import time
from typing import Any, cast, Optional, Union

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.timer import Timer

logger = logging.getLogger(__name__)

########################################################################
# type aliases
########################################################################
IntFloat = Union[int, float]
OptIntFloat = Optional[IntFloat]


########################################################################
# Timer test exceptions
########################################################################
class ErrorTstTimer(Exception):
    """Base class for exception in this module."""
    pass

########################################################################
# timeout_arg fixture
########################################################################
zero_or_less_timeout_arg_list = [-1.1, -1, 0, 0.0]
greater_than_zero_timeout_arg_list = [0.3, 0.5, 1, 1.5, 2, 4]


@pytest.fixture(params=zero_or_less_timeout_arg_list)  # type: ignore
def zero_or_less_timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


@pytest.fixture(params=greater_than_zero_timeout_arg_list)  # type: ignore
def greater_than_zero_timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


@pytest.fixture(params=zero_or_less_timeout_arg_list)  # type: ignore
def zero_or_less_default_timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout_default.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


@pytest.fixture(params=greater_than_zero_timeout_arg_list)  # type: ignore
def greater_than_zero_default_timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout_default.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


###############################################################################
# TestTimerExamples class
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

###############################################################################
# TestTimerBasic class
###############################################################################
class TestTimerBasic:
    """Test basic functions of Timer."""

    ###########################################################################
    # test_timer_case1a
    ###########################################################################
    def test_timer_case1a(self) -> None:
        """Test timer case1a."""
        print('mainline entered')
        timer = Timer()
        time.sleep(1)
        assert not timer.is_expired()
        time.sleep(1)
        assert not timer.is_expired()
        print('mainline exiting')
        
    ###########################################################################
    # test_timer_case1b
    ###########################################################################
    def test_timer_case1b(self) -> None:
        """Test timer case1b."""
        print('mainline entered')
        timer = Timer(default_timeout=None)
        time.sleep(1)
        assert not timer.is_expired()
        time.sleep(1)
        assert not timer.is_expired()
        print('mainline exiting')
        
    ###########################################################################
    # test_timer_case1c
    ###########################################################################
    def test_timer_case1c(self) -> None:
        """Test timer case1c."""
        print('mainline entered')
        timer = Timer(timeout=None)
        time.sleep(1)
        assert not timer.is_expired()
        time.sleep(1)
        assert not timer.is_expired()
        print('mainline exiting')
        
    ###########################################################################
    # test_timer_case1d
    ###########################################################################
    def test_timer_case1d(self) -> None:
        """Test timer case1d."""
        print('mainline entered')
        timer = Timer(timeout=None, default_timeout=None)
        time.sleep(1)
        assert not timer.is_expired()
        time.sleep(1)
        assert not timer.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_timer_case2a
    ###########################################################################
    def test_timer_case2a(self,
                          zero_or_less_default_timeout_arg: IntFloat
                          ) -> None:
        """Test timer case2a.

        Args:
            zero_or_less_default_timeout_arg: pytest fixture for timeout
                                                seconds

        """
        print('mainline entered')
        timer = Timer(default_timeout=zero_or_less_default_timeout_arg)
        time.sleep(abs(zero_or_less_default_timeout_arg * 0.9))
        assert not timer.is_expired()
        time.sleep(abs(zero_or_less_default_timeout_arg))
        assert not timer.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_timer_case2b
    ###########################################################################

    def test_timer_case2b(self,
                          zero_or_less_default_timeout_arg: IntFloat
                          ) -> None:
        """Test timer case2b.

        Args:
            zero_or_less_default_timeout_arg: pytest fixture for timeout
                                                seconds

        """
        print('mainline entered')
        timer = Timer(timeout=None,
                      default_timeout=zero_or_less_default_timeout_arg)
        time.sleep(abs(zero_or_less_default_timeout_arg * 0.9))
        assert not timer.is_expired()
        time.sleep(abs(zero_or_less_default_timeout_arg))
        assert not timer.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_timer_case3a
    ###########################################################################
    def test_timer_case3a(self,
                          greater_than_zero_default_timeout_arg: IntFloat
                          ) -> None:
        """Test timer case3a.

        Args:
            greater_than_zero_default_timeout_arg: pytest fixture for
                                                     timeout seconds

        """
        print('mainline entered')
        timer = Timer(default_timeout=greater_than_zero_default_timeout_arg)
        time.sleep(greater_than_zero_default_timeout_arg * 0.9)
        assert not timer.is_expired()
        time.sleep(greater_than_zero_default_timeout_arg)
        assert timer.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_timer_case3b
    ###########################################################################
    def test_timer_case3b(self,
                          greater_than_zero_default_timeout_arg: IntFloat
                          ) -> None:
        """Test timer case3b.

        Args:
            greater_than_zero_default_timeout_arg: pytest fixture for
                                                     timeout seconds

        """
        print('mainline entered')
        timer = Timer(timeout=None,
                      default_timeout=greater_than_zero_default_timeout_arg)
        time.sleep(greater_than_zero_default_timeout_arg * 0.9)
        assert not timer.is_expired()
        time.sleep(greater_than_zero_default_timeout_arg)
        assert timer.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_timer_case4a
    ###########################################################################
    def test_timer_case4a(self,
                          zero_or_less_timeout_arg: IntFloat) -> None:
        """Test timer case4a.

        Args:
            zero_or_less_timeout_arg: pytest fixture for timeout seconds

        """
        print('mainline entered')
        timer = Timer(timeout=zero_or_less_timeout_arg)
        time.sleep(abs(zero_or_less_timeout_arg * 0.9))
        assert not timer.is_expired()
        time.sleep(abs(zero_or_less_timeout_arg))
        assert not timer.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_timer_case4b
    ###########################################################################
    def test_timer_case4b(self,
                          zero_or_less_timeout_arg: IntFloat) -> None:
        """Test timer case4b.

        Args:
            zero_or_less_timeout_arg: pytest fixture for timeout seconds

        """
        print('mainline entered')
        timer = Timer(timeout=zero_or_less_timeout_arg,
                      default_timeout=None)
        time.sleep(abs(zero_or_less_timeout_arg * 0.9))
        assert not timer.is_expired()
        time.sleep(abs(zero_or_less_timeout_arg))
        assert not timer.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_timer_case5
    ###########################################################################
    def test_timer_case5(self,
                         zero_or_less_timeout_arg: IntFloat,
                         zero_or_less_default_timeout_arg: IntFloat
                         ) -> None:
        """Test timer case5.

        Args:
            zero_or_less_timeout_arg: pytest fixture for timeout seconds
            zero_or_less_default_timeout_arg: pytest fixture for timeout
                                                seconds

        """
        print('mainline entered')
        timer = Timer(timeout=zero_or_less_timeout_arg,
                      default_timeout=zero_or_less_default_timeout_arg)
        time.sleep(abs(zero_or_less_timeout_arg * 0.9))
        assert not timer.is_expired()
        time.sleep(abs(zero_or_less_timeout_arg))
        assert not timer.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_timer_case6
    ###########################################################################
    def test_timer_case6(self,
                         zero_or_less_timeout_arg: IntFloat,
                         greater_than_zero_default_timeout_arg: IntFloat
                         ) -> None:
        """Test timer case6.

        Args:
            zero_or_less_timeout_arg: pytest fixture for timeout seconds
            greater_than_zero_default_timeout_arg: pytest fixture for
                                                     timeout seconds

        """
        print('mainline entered')
        timer = Timer(timeout=zero_or_less_timeout_arg,
                      default_timeout=greater_than_zero_default_timeout_arg)
        time.sleep(abs(zero_or_less_timeout_arg * 0.9))
        assert not timer.is_expired()
        time.sleep(abs(zero_or_less_timeout_arg))
        assert not timer.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_timer_case7a
    ###########################################################################
    def test_timer_case7a(self,
                          greater_than_zero_timeout_arg: IntFloat) -> None:
        """Test timer case7a.

        Args:
            greater_than_zero_timeout_arg: pytest fixture for timeout
                                             seconds

        """
        print('mainline entered')
        timer = Timer(timeout=greater_than_zero_timeout_arg)
        time.sleep(greater_than_zero_timeout_arg * 0.9)
        assert not timer.is_expired()
        time.sleep(greater_than_zero_timeout_arg)
        assert timer.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_timer_case7b
    ###########################################################################
    def test_timer_case7b(self,
                          greater_than_zero_timeout_arg: IntFloat) -> None:
        """Test timer case7b.

        Args:
            greater_than_zero_timeout_arg: pytest fixture for timeout
                                             seconds

        """
        print('mainline entered')
        timer = Timer(timeout=greater_than_zero_timeout_arg,
                      default_timeout=None)
        time.sleep(greater_than_zero_timeout_arg * 0.9)
        assert not timer.is_expired()
        time.sleep(greater_than_zero_timeout_arg)
        assert timer.is_expired()
        print('mainline exiting')
        
    ###########################################################################
    # test_timer_case8
    ###########################################################################
    def test_timer_case8(self,
                         greater_than_zero_timeout_arg: IntFloat,
                         zero_or_less_default_timeout_arg: IntFloat
                         ) -> None:
        """Test timer case8.

        Args:
            greater_than_zero_timeout_arg: pytest fixture for timeout
                                             seconds
            zero_or_less_default_timeout_arg: pytest fixture for timeout
                                                seconds                                  

        """
        print('mainline entered')
        timer = Timer(timeout=greater_than_zero_timeout_arg, 
                      default_timeout=zero_or_less_default_timeout_arg)
        time.sleep(greater_than_zero_timeout_arg * 0.9)
        assert not timer.is_expired()
        time.sleep(greater_than_zero_timeout_arg)
        assert timer.is_expired()
        print('mainline exiting')
        
    ###########################################################################
    # test_timer_case9
    ###########################################################################
    def test_timer_case9(self,
                         greater_than_zero_timeout_arg: IntFloat,
                         greater_than_zero_default_timeout_arg: IntFloat
                         ) -> None:
        """Test timer case9.

        Args:
            greater_than_zero_timeout_arg: pytest fixture for timeout
                                             seconds
            greater_than_zero_default_timeout_arg: pytest fixture for 
                                                     timeout seconds                                 

        """
        print('mainline entered')
        timer = Timer(timeout=greater_than_zero_timeout_arg, 
                      default_timeout=greater_than_zero_default_timeout_arg)
        time.sleep(greater_than_zero_timeout_arg * 0.9)
        assert not timer.is_expired()
        time.sleep(greater_than_zero_timeout_arg)
        assert timer.is_expired()
        print('mainline exiting')

