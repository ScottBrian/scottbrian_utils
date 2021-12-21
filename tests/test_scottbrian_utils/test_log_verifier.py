"""test_log_verifier.py module."""

########################################################################
# Standard Library
########################################################################
import logging
import threading
import time
from typing import Any, cast, Optional, Union

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.log_verifier import LogVer

logger = logging.getLogger(__name__)

########################################################################
# type aliases
########################################################################
IntFloat = Union[int, float]
OptIntFloat = Optional[IntFloat]


########################################################################
# LogVer test exceptions
########################################################################
class ErrorTstLogVer(Exception):
    """Base class for exception in this module."""
    pass


########################################################################
# timeout arg fixtures
# greater_than_zero_timeout_arg fixture
########################################################################
zero_or_less_timeout_arg_list = [-1.1, -1, 0, 0.0]
greater_than_zero_timeout_arg_list = [0.3, 0.5, 1, 1.5, 2, 4]


########################################################################
# timeout_arg fixture
########################################################################
@pytest.fixture(params=greater_than_zero_timeout_arg_list)  # type: ignore
def timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


########################################################################
# zero_or_less_timeout_arg fixture
########################################################################
@pytest.fixture(params=zero_or_less_timeout_arg_list)  # type: ignore
def zero_or_less_timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


########################################################################
# greater_than_zero_timeout_arg fixture
########################################################################
@pytest.fixture(params=greater_than_zero_timeout_arg_list)  # type: ignore
def greater_than_zero_timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


########################################################################
# zero_or_less_default_timeout_arg fixture
########################################################################
@pytest.fixture(params=zero_or_less_timeout_arg_list)  # type: ignore
def zero_or_less_default_timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout_default.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


########################################################################
# greater_than_zero_default_timeout_arg fixture
########################################################################
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
# TestLogVerExamples class
###############################################################################
class TestLogVerExamples:
    """Test examples of LogVer."""

    ###########################################################################
    # test_log_verifier_example1
    ###########################################################################
    def test_log_verifier_example1(self,
                                   capsys: Any,
                                   caplog: Any) -> None:
        """Test log_verifier example1.

        Args:
            capsys: pytest fixture to capture print output

        """
        logger = logging.getLogger(__name__)
        log_ver = LogVer()
        log_msg = 'hello'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)
        log_ver.verify_log_msgs(caplog)
        expected_result = '\nnum_log_records_found: 1 of 1\n'
        expected_result += '******** matched log records found ********\n'
        expected_result += 'hello\n'
        expected_result += ('******** remaining unmatched log records '
                            '********\n')
        expected_result += '******** remaining expected log records ********\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ###########################################################################
    # test_log_verifier_example2
    ###########################################################################
    def test_log_verifier_example2(self,
                            capsys: Any) -> None:
        """Test log_verifier example2.

        Args:
            capsys: pytest fixture to capture print output

        """
        class A:
            def __init__(self):
                self.a = 1

            def m1(self, sleep_time: float) -> bool:
                log_verifier = LogVer(timeout=1)
                time.sleep(sleep_time)
                if log_verifier.is_expired():
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
    # test_log_verifier_example3
    ###########################################################################
    def test_log_verifier_example3(self,
                            capsys: Any) -> None:
        """Test log_verifier example3.

        Args:
            capsys: pytest fixture to capture print output

        """
        class A:
            def __init__(self):
                self.a = 1

            def m1(self, sleep_time: float, timeout: float) -> bool:
                log_verifier = LogVer(timeout=timeout)
                time.sleep(sleep_time)
                if log_verifier.is_expired():
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
    # test_log_verifier_example4
    ###########################################################################
    def test_log_verifier_example4(self,
                            capsys: Any) -> None:
        """Test log_verifier example4.

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
                log_verifier = LogVer(timeout=timeout,
                              default_timeout=self.default_timeout)
                time.sleep(sleep_time)
                if log_verifier.is_expired():
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
    # test_log_verifier_example5
    ###########################################################################
    def test_log_verifier_example5(self,
                            capsys: Any) -> None:
        """Test log_verifier example5.

        Args:
            capsys: pytest fixture to capture print output

        """
        def f1():
            print('f1 entered')
            time.sleep(1)
            f1_event.set()
            time.sleep(1)
            f1_event.set()
            time.sleep(1)
            f1_event.set()
            print('f1 exiting')

        print('mainline entered')
        log_verifier = LogVer(timeout=2.5)
        f1_thread = threading.Thread(target=f1)
        f1_event = threading.Event()
        f1_thread.start()
        wait_result = f1_event.wait(timeout=log_verifier.remaining_time())
        print(f'wait1 result = {wait_result}')
        f1_event.clear()
        print(f'remaining time = {log_verifier.remaining_time():0.1f}')
        print(f'log_verifier expired = {log_verifier.is_expired()}')
        wait_result = f1_event.wait(timeout=log_verifier.remaining_time())
        print(f'wait2 result = {wait_result}')
        f1_event.clear()
        print(f'remaining time = {log_verifier.remaining_time():0.1f}')
        print(f'log_verifier expired = {log_verifier.is_expired()}')
        wait_result = f1_event.wait(timeout=log_verifier.remaining_time())
        print(f'wait3 result = {wait_result}')
        f1_event.clear()
        print(f'remaining time = {log_verifier.remaining_time():0.4f}')
        print(f'log_verifier expired = {log_verifier.is_expired()}')
        f1_thread.join()
        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += 'f1 entered\n'
        expected_result += 'wait1 result = True\n'
        expected_result += 'remaining time = 1.5\n'
        expected_result += 'log_verifier expired = False\n'
        expected_result += 'wait2 result = True\n'
        expected_result += 'remaining time = 0.5\n'
        expected_result += 'log_verifier expired = False\n'
        expected_result += 'wait3 result = False\n'
        expected_result += 'remaining time = 0.0001\n'
        expected_result += 'log_verifier expired = True\n'
        expected_result += 'f1 exiting\n'
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ###########################################################################
    # test_log_verifier_example6
    ###########################################################################
    def test_log_verifier_example6(self,
                            capsys: Any) -> None:
        """Test log_verifier example6.

        Args:
            capsys: pytest fixture to capture print output

        """
        print('mainline entered')
        log_verifier = LogVer(timeout=2.5)
        time.sleep(1)
        print(f'log_verifier expired = {log_verifier.is_expired()}')
        time.sleep(1)
        print(f'log_verifier expired = {log_verifier.is_expired()}')
        time.sleep(1)
        print(f'log_verifier expired = {log_verifier.is_expired()}')
        print('mainline exiting')

        expected_result = 'mainline entered\n'
        expected_result += 'log_verifier expired = False\n'
        expected_result += 'log_verifier expired = False\n'
        expected_result += 'log_verifier expired = True\n'
        expected_result += 'mainline exiting\n'

        captured = capsys.readouterr().out

        assert captured == expected_result


###############################################################################
# TestLogVerBasic class
###############################################################################
class TestLogVerBasic:
    """Test basic functions of LogVer."""

    ###########################################################################
    # test_log_verifier_case1a
    ###########################################################################
    def test_log_verifier_case1a(self) -> None:
        """Test log_verifier case1a."""
        print('mainline entered')
        log_verifier = LogVer()
        time.sleep(1)
        assert not log_verifier.is_expired()
        time.sleep(1)
        assert not log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case1b
    ###########################################################################
    def test_log_verifier_case1b(self) -> None:
        """Test log_verifier case1b."""
        print('mainline entered')
        log_verifier = LogVer(default_timeout=None)
        time.sleep(1)
        assert not log_verifier.is_expired()
        time.sleep(1)
        assert not log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case1c
    ###########################################################################
    def test_log_verifier_case1c(self) -> None:
        """Test log_verifier case1c."""
        print('mainline entered')
        log_verifier = LogVer(timeout=None)
        time.sleep(1)
        assert not log_verifier.is_expired()
        time.sleep(1)
        assert not log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case1d
    ###########################################################################
    def test_log_verifier_case1d(self) -> None:
        """Test log_verifier case1d."""
        print('mainline entered')
        log_verifier = LogVer(timeout=None, default_timeout=None)
        time.sleep(1)
        assert not log_verifier.is_expired()
        time.sleep(1)
        assert not log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case2a
    ###########################################################################
    def test_log_verifier_case2a(self,
                          zero_or_less_default_timeout_arg: IntFloat
                          ) -> None:
        """Test log_verifier case2a.

        Args:
            zero_or_less_default_timeout_arg: pytest fixture for timeout
                                                seconds

        """
        print('mainline entered')
        log_verifier = LogVer(default_timeout=zero_or_less_default_timeout_arg)
        time.sleep(abs(zero_or_less_default_timeout_arg * 0.9))
        assert not log_verifier.is_expired()
        time.sleep(abs(zero_or_less_default_timeout_arg))
        assert not log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case2b
    ###########################################################################

    def test_log_verifier_case2b(self,
                          zero_or_less_default_timeout_arg: IntFloat
                          ) -> None:
        """Test log_verifier case2b.

        Args:
            zero_or_less_default_timeout_arg: pytest fixture for timeout
                                                seconds

        """
        print('mainline entered')
        log_verifier = LogVer(timeout=None,
                      default_timeout=zero_or_less_default_timeout_arg)
        time.sleep(abs(zero_or_less_default_timeout_arg * 0.9))
        assert not log_verifier.is_expired()
        time.sleep(abs(zero_or_less_default_timeout_arg))
        assert not log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case3a
    ###########################################################################
    def test_log_verifier_case3a(self,
                          greater_than_zero_default_timeout_arg: IntFloat
                          ) -> None:
        """Test log_verifier case3a.

        Args:
            greater_than_zero_default_timeout_arg: pytest fixture for
                                                     timeout seconds

        """
        print('mainline entered')
        log_verifier = LogVer(default_timeout=greater_than_zero_default_timeout_arg)
        time.sleep(greater_than_zero_default_timeout_arg * 0.9)
        assert not log_verifier.is_expired()
        time.sleep(greater_than_zero_default_timeout_arg)
        assert log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case3b
    ###########################################################################
    def test_log_verifier_case3b(self,
                          greater_than_zero_default_timeout_arg: IntFloat
                          ) -> None:
        """Test log_verifier case3b.

        Args:
            greater_than_zero_default_timeout_arg: pytest fixture for
                                                     timeout seconds

        """
        print('mainline entered')
        log_verifier = LogVer(timeout=None,
                      default_timeout=greater_than_zero_default_timeout_arg)
        time.sleep(greater_than_zero_default_timeout_arg * 0.9)
        assert not log_verifier.is_expired()
        time.sleep(greater_than_zero_default_timeout_arg)
        assert log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case4a
    ###########################################################################
    def test_log_verifier_case4a(self,
                          zero_or_less_timeout_arg: IntFloat) -> None:
        """Test log_verifier case4a.

        Args:
            zero_or_less_timeout_arg: pytest fixture for timeout seconds

        """
        print('mainline entered')
        log_verifier = LogVer(timeout=zero_or_less_timeout_arg)
        time.sleep(abs(zero_or_less_timeout_arg * 0.9))
        assert not log_verifier.is_expired()
        time.sleep(abs(zero_or_less_timeout_arg))
        assert not log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case4b
    ###########################################################################
    def test_log_verifier_case4b(self,
                          zero_or_less_timeout_arg: IntFloat) -> None:
        """Test log_verifier case4b.

        Args:
            zero_or_less_timeout_arg: pytest fixture for timeout seconds

        """
        print('mainline entered')
        log_verifier = LogVer(timeout=zero_or_less_timeout_arg,
                      default_timeout=None)
        time.sleep(abs(zero_or_less_timeout_arg * 0.9))
        assert not log_verifier.is_expired()
        time.sleep(abs(zero_or_less_timeout_arg))
        assert not log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case5
    ###########################################################################
    def test_log_verifier_case5(self,
                         zero_or_less_timeout_arg: IntFloat,
                         zero_or_less_default_timeout_arg: IntFloat
                         ) -> None:
        """Test log_verifier case5.

        Args:
            zero_or_less_timeout_arg: pytest fixture for timeout seconds
            zero_or_less_default_timeout_arg: pytest fixture for timeout
                                                seconds

        """
        print('mainline entered')
        log_verifier = LogVer(timeout=zero_or_less_timeout_arg,
                      default_timeout=zero_or_less_default_timeout_arg)
        time.sleep(abs(zero_or_less_timeout_arg * 0.9))
        assert not log_verifier.is_expired()
        time.sleep(abs(zero_or_less_timeout_arg))
        assert not log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case6
    ###########################################################################
    def test_log_verifier_case6(self,
                         zero_or_less_timeout_arg: IntFloat,
                         greater_than_zero_default_timeout_arg: IntFloat
                         ) -> None:
        """Test log_verifier case6.

        Args:
            zero_or_less_timeout_arg: pytest fixture for timeout seconds
            greater_than_zero_default_timeout_arg: pytest fixture for
                                                     timeout seconds

        """
        print('mainline entered')
        log_verifier = LogVer(timeout=zero_or_less_timeout_arg,
                      default_timeout=greater_than_zero_default_timeout_arg)
        time.sleep(abs(zero_or_less_timeout_arg * 0.9))
        assert not log_verifier.is_expired()
        time.sleep(abs(zero_or_less_timeout_arg))
        assert not log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case7a
    ###########################################################################
    def test_log_verifier_case7a(self,
                          greater_than_zero_timeout_arg: IntFloat) -> None:
        """Test log_verifier case7a.

        Args:
            greater_than_zero_timeout_arg: pytest fixture for timeout
                                             seconds

        """
        print('mainline entered')
        log_verifier = LogVer(timeout=greater_than_zero_timeout_arg)
        time.sleep(greater_than_zero_timeout_arg * 0.9)
        assert not log_verifier.is_expired()
        time.sleep(greater_than_zero_timeout_arg)
        assert log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case7b
    ###########################################################################
    def test_log_verifier_case7b(self,
                          greater_than_zero_timeout_arg: IntFloat) -> None:
        """Test log_verifier case7b.

        Args:
            greater_than_zero_timeout_arg: pytest fixture for timeout
                                             seconds

        """
        print('mainline entered')
        log_verifier = LogVer(timeout=greater_than_zero_timeout_arg,
                      default_timeout=None)
        time.sleep(greater_than_zero_timeout_arg * 0.9)
        assert not log_verifier.is_expired()
        time.sleep(greater_than_zero_timeout_arg)
        assert log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case8
    ###########################################################################
    def test_log_verifier_case8(self,
                         greater_than_zero_timeout_arg: IntFloat,
                         zero_or_less_default_timeout_arg: IntFloat
                         ) -> None:
        """Test log_verifier case8.

        Args:
            greater_than_zero_timeout_arg: pytest fixture for timeout
                                             seconds
            zero_or_less_default_timeout_arg: pytest fixture for timeout
                                                seconds

        """
        print('mainline entered')
        log_verifier = LogVer(timeout=greater_than_zero_timeout_arg,
                      default_timeout=zero_or_less_default_timeout_arg)
        time.sleep(greater_than_zero_timeout_arg * 0.9)
        assert not log_verifier.is_expired()
        time.sleep(greater_than_zero_timeout_arg)
        assert log_verifier.is_expired()
        print('mainline exiting')

    ###########################################################################
    # test_log_verifier_case9
    ###########################################################################
    def test_log_verifier_case9(self,
                         greater_than_zero_timeout_arg: IntFloat,
                         greater_than_zero_default_timeout_arg: IntFloat
                         ) -> None:
        """Test log_verifier case9.

        Args:
            greater_than_zero_timeout_arg: pytest fixture for timeout
                                             seconds
            greater_than_zero_default_timeout_arg: pytest fixture for
                                                     timeout seconds
        """
        print('mainline entered')
        log_verifier = LogVer(timeout=greater_than_zero_timeout_arg,
                      default_timeout=greater_than_zero_default_timeout_arg)
        time.sleep(greater_than_zero_timeout_arg * 0.9)
        assert not log_verifier.is_expired()
        time.sleep(greater_than_zero_timeout_arg)
        assert log_verifier.is_expired()
        print('mainline exiting')


###############################################################################
# TestLogVerBasic class
###############################################################################
class TestLogVerRemainingTime:
    """Test remaining_time method of LogVer."""

    ###########################################################################
    # test_log_verifier_remaining_time1
    ###########################################################################
    def test_log_verifier_remaining_time1(self,
                                   timeout_arg) -> None:
        """Test log_verifier remaining time1.

        Args:
            timeout_arg: number of seconds to use for log_verifier timeout arg

        """
        logger.debug('mainline entered')
        sleep_time = timeout_arg/3
        log_verifier = LogVer(timeout=timeout_arg)
        time.sleep(sleep_time)
        exp_remaining_time = timeout_arg - sleep_time

        assert ((exp_remaining_time * .9)
                <= log_verifier.remaining_time()
                <= exp_remaining_time)
        assert not log_verifier.is_expired()

        time.sleep(sleep_time)
        exp_remaining_time = timeout_arg - sleep_time * 2

        assert ((exp_remaining_time * .9)
                <= log_verifier.remaining_time()
                <= exp_remaining_time)
        assert not log_verifier.is_expired()

        time.sleep(sleep_time + 0.1)
        exp_remaining_time = 0.0001

        assert exp_remaining_time == log_verifier.remaining_time()
        assert log_verifier.is_expired()

        logger.debug('mainline exiting')
