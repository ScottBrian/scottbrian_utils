"""test_log_verifier.py module."""

########################################################################
# Standard Library
########################################################################
import logging
import datetime
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
        # one message expected, one message logged
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
        # one message expected, two messages logged
        t_logger = logging.getLogger(__name__)
        log_ver = LogVer()
        log_msg1 = 'hello'
        log_ver.add_msg(log_msg=log_msg1)
        log_msg2 = 'goodbye'
        t_logger.debug(log_msg1)
        t_logger.debug(log_msg2)
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

    ####################################################################
    # test_log_verifier_example4
    ####################################################################
    def test_log_verifier_example4(self,
                                   capsys: Any,
                                   caplog: Any) -> None:
        """Test log_verifier example4.

        Args:
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output

        """
        # two log messages expected, two logged, one different
        # logged
        t_logger = logging.getLogger(__name__)
        log_ver = LogVer()
        log_msg1 = 'hello'
        log_ver.add_msg(log_msg=log_msg1)
        log_msg2a = 'goodbye'
        log_ver.add_msg(log_msg=log_msg2a)
        log_msg2b = 'see you soon'
        logger.debug(log_msg1)
        logger.debug(log_msg2b)
        log_ver.print_match_results(
            log_results := log_ver.get_match_results(caplog))
        with pytest.raises(UnmatchedExpectedMessages):
            log_ver.verify_log_results(log_results)

        expected_result = '\n'
        expected_result += '**********************************\n'
        expected_result += '* number expected log records: 2 *\n'
        expected_result += '* number expected unmatched  : 1 *\n'
        expected_result += '* number actual log records  : 2 *\n'
        expected_result += '* number actual unmatched    : 1 *\n'
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
        expected_result += 'see you soon\n'
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
    def test_log_verifier_time_match(self,
                                     capsys: Any,
                                     caplog: Any) -> None:
        """Test log_verifier case1a."""
        t_logger = logging.getLogger(__name__)
        log_ver = LogVer()
        fmt_str = '%d %b %Y %H:%M:%S'

        match_str_d = r'([0-2][0-9]|3[0-1])'
        match_str_b = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        match_str_Y = r'[2-9][0-9]{3,3}'
        match_str_H = r'([0-1][0-9]|2[0-3])'
        match_str_M_S = r'[0-5][0-9]'
        match_str = (f'{match_str_d} {match_str_b} {match_str_Y} '
                     f'{match_str_H}:{match_str_M_S}:{match_str_M_S}')

        time_str = datetime.datetime.now().strftime(fmt_str)

        exp_msg = f'the date and time is: {match_str}'
        act_msg = f'the date and time is: {time_str}'
        log_ver.add_msg(log_msg=exp_msg)
        logger.debug(act_msg)
        log_ver.print_match_results(
            log_results := log_ver.get_match_results(caplog))
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
        expected_result += f'the date and time is: {time_str}\n'

        captured = capsys.readouterr().out

        assert captured == expected_result


###############################################################################
# TestLogVerBasic class
###############################################################################
class TestLogVerCombos:
    """Test LogVer with various combinations."""

    ###########################################################################
    # test_log_verifier_remaining_time1
    ###########################################################################
    def test_log_verifier_combos(self,
                                 timeout_arg) -> None:
        """Test log_verifier combos.

        Args:
            timeout_arg: number of seconds to use for log_verifier timeout arg

        """
        logger.debug('mainline entered')

        logger.debug('mainline exiting')
