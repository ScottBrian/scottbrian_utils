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
import numpy as np

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
# number of log messages arg fixtures
########################################################################
num_msgs_arg_list = [0, 1, 2, 3]


@pytest.fixture(params=num_msgs_arg_list)  # type: ignore
def num_exp_msgs1(request: Any) -> int:
    """Using different number of messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=num_msgs_arg_list)  # type: ignore
def num_exp_msgs2(request: Any) -> int:
    """Using different number of messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=num_msgs_arg_list)  # type: ignore
def num_exp_msgs3(request: Any) -> int:
    """Using different number of messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=num_msgs_arg_list)  # type: ignore
def num_act_msgs1(request: Any) -> int:
    """Using different number of messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=num_msgs_arg_list)  # type: ignore
def num_act_msgs2(request: Any) -> int:
    """Using different number of messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=num_msgs_arg_list)  # type: ignore
def num_act_msgs3(request: Any) -> int:
    """Using different number of messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


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
        """Test log_verifier time match.

        Args:
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
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
                                 num_exp_msgs1: int,
                                 num_exp_msgs2: int,
                                 num_exp_msgs3: int,
                                 num_act_msgs1: int,
                                 num_act_msgs2: int,
                                 num_act_msgs3: int,
                                 capsys: Any,
                                 caplog: Any
                                 ) -> None:
        """Test log_verifier combos.

        Args:
            num_exp_msgs1: number of expected messages for msg1
            num_exp_msgs2: number of expected messages for msg2
            num_exp_msgs3: number of expected messages for msg3
            num_act_msgs1: number of actual messages for msg1
            num_act_msgs2: number of actual messages for msg2
            num_act_msgs3: number of actual messages for msg3
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output

        """
        t_logger = logging.getLogger(__name__)
        log_ver = LogVer()

        total_num_exp_msgs = 0
        total_num_act_msgs = 0
        total_num_exp_unmatched = 0
        total_num_act_unmatched = 0
        total_num_matched = 0

        exp_unmatched_msgs = []
        act_unmatched_msgs = []
        matched_msgs = []

        msg_table = [(num_exp_msgs1, num_act_msgs1, 'msg one'),
                     (num_exp_msgs2, num_act_msgs2, 'msg two'),
                     (num_exp_msgs3, num_act_msgs3, 'msg three')]

        for num_exp, num_act, the_msg in msg_table:
            total_num_exp_msgs += num_exp
            total_num_act_msgs += num_act
            num_exp_unmatched = max(0, num_exp - num_act)
            total_num_exp_unmatched += num_exp_unmatched
            num_act_unmatched = max(0, num_act - num_exp)
            total_num_act_unmatched += num_act_unmatched
            num_matched_msgs = num_exp - num_exp_unmatched
            total_num_matched += num_matched_msgs

            for _ in range(num_exp):
                log_ver.add_msg(log_msg=the_msg)

            for _ in range(num_act):
                logger.debug(the_msg)

            for _ in range(num_exp_unmatched):
                exp_unmatched_msgs.append(the_msg)

            for _ in range(num_act_unmatched):
                act_unmatched_msgs.append(the_msg)

            for _ in range(num_matched_msgs):
                matched_msgs.append(the_msg)

        max_of_totals = max(total_num_exp_msgs,
                            total_num_act_msgs,
                            total_num_exp_unmatched,
                            total_num_act_unmatched,
                            total_num_matched)

        len_max_total = len(str(max_of_totals))
        asterisks = '*********************************' + '*' * len_max_total

        num_exp_space = len_max_total - len(str(total_num_exp_msgs))
        num_exp_unm_space = len_max_total - len(str(total_num_exp_unmatched))
        num_act_space = len_max_total - len(str(total_num_act_msgs))
        num_act_unm_space = len_max_total - len(str(total_num_act_unmatched))
        num_matched_space = len_max_total - len(str(total_num_matched))

        log_ver.print_match_results(
            log_results := log_ver.get_match_results(caplog))

        if total_num_exp_unmatched:
            with pytest.raises(UnmatchedExpectedMessages):
                log_ver.verify_log_results(log_results)
        elif total_num_act_unmatched:
            with pytest.raises(UnmatchedActualMessages):
                log_ver.verify_log_results(log_results)
        else:
            log_ver.verify_log_results(log_results)

        expected_result = '\n'
        expected_result += asterisks + '\n'
        expected_result += ('* number expected log records: '
                            + ' ' * num_exp_space
                            + f'{total_num_exp_msgs} *\n')
        expected_result += ('* number expected unmatched  : '
                            + ' ' * num_exp_unm_space
                            + f'{total_num_exp_unmatched} *\n')
        expected_result += ('* number actual log records  : '
                            + ' ' * num_act_space
                            + f'{total_num_act_msgs} *\n')
        expected_result += ('* number actual unmatched    : '
                            + ' ' * num_act_unm_space
                            + f'{total_num_act_unmatched} *\n')
        expected_result += (f'* number matched records     : '
                            + ' ' * num_matched_space
                            + f'{total_num_matched} *\n')
        expected_result += asterisks + '\n'
        expected_result += '\n'
        expected_result += '******************************\n'
        expected_result += '* unmatched expected records *\n'
        expected_result += '******************************\n'

        for msg in exp_unmatched_msgs:
            expected_result += msg + '\n'

        expected_result += '\n'
        expected_result += '****************************\n'
        expected_result += '* unmatched actual records *\n'
        expected_result += '****************************\n'

        for msg in act_unmatched_msgs:
            expected_result += msg + '\n'

        expected_result += '\n'
        expected_result += '***********************\n'
        expected_result += '* matched log records *\n'
        expected_result += '***********************\n'

        for msg in matched_msgs:
            expected_result += msg + '\n'

        captured = capsys.readouterr().out

        assert captured == expected_result
