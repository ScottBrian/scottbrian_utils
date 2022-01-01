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
from scottbrian_utils.log_verifier import UnmatchedExpectedMessages
from scottbrian_utils.log_verifier import UnmatchedActualMessages

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


########################################################################
# TestLogVerExamples class
########################################################################
class TestLogVerExamples:
    """Test examples of LogVer."""

    ####################################################################
    # test_log_verifier_example1
    ####################################################################
    def test_log_verifier_example1(self,
                                   capsys: Any,
                                   caplog: Any) -> None:
        """Test log_verifier example1.

        Args:
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output

        """
        t_logger = logging.getLogger(__name__)
        log_ver = LogVer()
        log_msg = 'hello'
        log_ver.add_msg(log_msg=log_msg)
        t_logger.debug(log_msg)
        log_results = log_ver.get_match_results(caplog)
        log_ver.print_match_results(log_results)
        log_ver.verify_log_results(log_results)

        expected_result = '\n'
        expected_result += '**********************************\n'
        expected_result += '* number expected log records: 1 *\n'
        expected_result += '* number expected unmatched  : 0 *\n'
        expected_result += '* number actual log records  : 1 *\n'
        expected_result += '* number actual unmatched    : 0 *\n'
        expected_result += '* number matched records     : 1 *\n'
        expected_result += '**********************************\n'
        expected_result += '\n'
        expected_result += '******************************\n'
        expected_result += '* unmatched expected records *\n'
        expected_result += '******************************\n'
        expected_result += '\n'
        expected_result += '****************************\n'
        expected_result += '* unmatched actual records *\n'
        expected_result += '****************************\n'
        expected_result += '\n'
        expected_result += '***********************\n'
        expected_result += '* matched log records *\n'
        expected_result += '***********************\n'
        expected_result += 'hello\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_example2
    ####################################################################
    def test_log_verifier_example2(self,
                                   capsys: Any,
                                   caplog: Any) -> None:
        """Test log_verifier example2.

        Args:
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output

        """
        # two log messages expected, only one is logged
        t_logger = logging.getLogger(__name__)
        log_ver = LogVer()
        log_msg1 = 'hello'
        log_ver.add_msg(log_msg=log_msg1)
        log_msg2 = 'goodbye'
        log_ver.add_msg(log_msg=log_msg2)
        t_logger.debug(log_msg1)
        log_results = log_ver.get_match_results(caplog)
        log_ver.print_match_results(log_results)
        with pytest.raises(UnmatchedExpectedMessages):
            log_ver.verify_log_results(log_results)

        expected_result = '\n'
        expected_result += '**********************************\n'
        expected_result += '* number expected log records: 2 *\n'
        expected_result += '* number expected unmatched  : 1 *\n'
        expected_result += '* number actual log records  : 1 *\n'
        expected_result += '* number actual unmatched    : 0 *\n'
        expected_result += '* number matched records     : 1 *\n'
        expected_result += '**********************************\n'
        expected_result += '\n'
        expected_result += '******************************\n'
        expected_result += '* unmatched expected records *\n'
        expected_result += '******************************\n'
        expected_result += 'goodbye\n'
        expected_result += '\n'
        expected_result += '****************************\n'
        expected_result += '* unmatched actual records *\n'
        expected_result += '****************************\n'
        expected_result += '\n'
        expected_result += '***********************\n'
        expected_result += '* matched log records *\n'
        expected_result += '***********************\n'
        expected_result += 'hello\n'

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_example3
    ####################################################################
    def test_log_verifier_example3(self,
                                   capsys: Any,
                                   caplog: Any) -> None:
        """Test log_verifier example3.

        Args:
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output

        """
        # two log messages expected, only one is logged
        t_logger = logging.getLogger(__name__)
        log_ver = LogVer()
        log_msg1 = 'hello'
        log_ver.add_msg(log_msg=log_msg1)
        log_msg2 = 'goodbye'
        t_logger.debug(log_msg1)
        t_logger.debug(log_msg2)
        # log_results = log_ver.get_match_results(caplog)
        log_ver.print_match_results(
            log_results := log_ver.get_match_results(caplog))
        with pytest.raises(UnmatchedActualMessages):
            log_ver.verify_log_results(log_results)

        expected_result = '\n'
        expected_result += '**********************************\n'
        expected_result += '* number expected log records: 1 *\n'
        expected_result += '* number expected unmatched  : 0 *\n'
        expected_result += '* number actual log records  : 2 *\n'
        expected_result += '* number actual unmatched    : 1 *\n'
        expected_result += '* number matched records     : 1 *\n'
        expected_result += '**********************************\n'
        expected_result += '\n'
        expected_result += '******************************\n'
        expected_result += '* unmatched expected records *\n'
        expected_result += '******************************\n'
        expected_result += '\n'
        expected_result += '****************************\n'
        expected_result += '* unmatched actual records *\n'
        expected_result += '****************************\n'
        expected_result += 'goodbye\n'
        expected_result += '\n'
        expected_result += '***********************\n'
        expected_result += '* matched log records *\n'
        expected_result += '***********************\n'
        expected_result += 'hello\n'

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
