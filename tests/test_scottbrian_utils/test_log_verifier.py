"""test_log_verifier.py module."""

########################################################################
# Standard Library
########################################################################
from collections.abc import Iterable
import itertools as it
import more_itertools as mi
import logging
import pandas as pd
import datetime
import re
import string
import threading
from typing import Any, cast, Optional, Union

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.log_verifier import LogVer
from scottbrian_utils.log_verifier import UnmatchedExpectedMessages
from scottbrian_utils.log_verifier import UnmatchedActualMessages
from scottbrian_utils.time_hdr import get_datetime_match_string

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
# log_enabled_arg
########################################################################
log_enabled_arg_list = [True, False]


@pytest.fixture(params=log_enabled_arg_list)
def log_enabled_arg(request: Any) -> bool:
    """Using enabled and disabled logging.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(bool, request.param)


########################################################################
# simple_str_arg
########################################################################
simple_str_arg_list = ["a", "ab", "a1", "xyz123"]


@pytest.fixture(params=simple_str_arg_list)
def simple_str_arg(request: Any) -> str:
    """Using different string messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(str, request.param)


########################################################################
# number of log messages arg fixtures
########################################################################
num_msgs_arg_list = [0, 1, 2, 3]


@pytest.fixture(params=num_msgs_arg_list)
def num_exp_msgs1(request: Any) -> int:
    """Using different number of messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=num_msgs_arg_list)
def num_exp_msgs2(request: Any) -> int:
    """Using different number of messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=num_msgs_arg_list)
def num_exp_msgs3(request: Any) -> int:
    """Using different number of messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=num_msgs_arg_list)
def num_act_msgs1(request: Any) -> int:
    """Using different number of messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=num_msgs_arg_list)
def num_act_msgs2(request: Any) -> int:
    """Using different number of messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=num_msgs_arg_list)
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
@pytest.mark.cover2
class TestLogVerExamples:
    """Test examples of LogVer."""

    ####################################################################
    # test_log_verifier_example1
    ####################################################################
    def test_log_verifier_example1(
        self, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test log_verifier example1.

        Args:
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output

        """
        # one message expected, one message logged
        t_logger = logging.getLogger("example_1")
        log_ver = LogVer(log_name="example_1")
        log_msg = "hello"
        log_ver.add_msg(log_msg=log_msg)
        t_logger.debug(log_msg)
        log_results = log_ver.get_match_results(caplog)
        log_ver.print_match_results(log_results)
        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 1 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 1 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "('example_1', 10, 'hello')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_example2
    ####################################################################
    def test_log_verifier_example2(
        self, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test log_verifier example2.

        Args:
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output

        """
        # two log messages expected, only one is logged
        t_logger = logging.getLogger("example_2")
        log_ver = LogVer(log_name="example_2")
        log_msg1 = "hello"
        log_ver.add_msg(log_msg=log_msg1)
        log_msg2 = "goodbye"
        log_ver.add_msg(log_msg=log_msg2)
        t_logger.debug(log_msg1)
        log_results = log_ver.get_match_results(caplog)
        log_ver.print_match_results(log_results)
        with pytest.raises(UnmatchedExpectedMessages):
            log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 1 *\n"
        expected_result += "* number actual log records  : 1 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "('example_2', 10, 'goodbye')\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "('example_2', 10, 'hello')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_example3
    ####################################################################
    def test_log_verifier_example3(
        self, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test log_verifier example3.

        Args:
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output

        """
        # one message expected, two messages logged
        t_logger = logging.getLogger("example_3")
        log_ver = LogVer(log_name="example_3")
        log_msg1 = "hello"
        log_ver.add_msg(log_msg=log_msg1)
        log_msg2 = "goodbye"
        t_logger.debug(log_msg1)
        t_logger.debug(log_msg2)
        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        with pytest.raises(UnmatchedActualMessages):
            log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 1 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 2 *\n"
        expected_result += "* number actual unmatched    : 1 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "('example_3', 10, 'goodbye')\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "('example_3', 10, 'hello')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_example4
    ####################################################################
    def test_log_verifier_example4(
        self, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test log_verifier example4.

        Args:
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output

        """
        # two log messages expected, two logged, one different
        # logged
        t_logger = logging.getLogger("example_4")
        log_ver = LogVer(log_name="example_4")
        log_msg1 = "hello"
        log_ver.add_msg(log_msg=log_msg1)
        log_msg2a = "goodbye"
        log_ver.add_msg(log_msg=log_msg2a)
        log_msg2b = "see you soon"
        t_logger.debug(log_msg1)
        t_logger.debug(log_msg2b)
        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        with pytest.raises(UnmatchedExpectedMessages):
            log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 1 *\n"
        expected_result += "* number actual log records  : 2 *\n"
        expected_result += "* number actual unmatched    : 1 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "('example_4', 10, 'goodbye')\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "('example_4', 10, 'see you soon')\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "('example_4', 10, 'hello')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_example5
    ####################################################################
    def test_log_verifier_example5(
        self, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test log_verifier example5 for add_msg.

        Args:
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output

        """
        # add two log messages, each different level
        t_logger = logging.getLogger("add_msg")
        log_ver = LogVer("add_msg")
        log_msg1 = "hello"
        log_msg2 = "goodbye"
        log_ver.add_msg(log_msg=log_msg1)
        log_ver.add_msg(log_msg=log_msg2, log_level=logging.ERROR)
        t_logger.debug(log_msg1)
        t_logger.error(log_msg2)
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 2 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 2 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "('add_msg', 10, 'hello')\n"
        expected_result += "('add_msg', 40, 'goodbye')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result


########################################################################
# TestLogVerBasic class
########################################################################
@pytest.mark.cover2
class TestLogVerBasic:
    """Test basic functions of LogVer."""

    ####################################################################
    # test_log_verifier_repr
    ####################################################################
    def test_log_verifier_repr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test log_verifier repr function.

        Args:
            capsys: pytest fixture to capture print output

        """
        log_ver = LogVer(log_name="simple_repr")
        print(log_ver)  # test of __repr__
        captured = capsys.readouterr().out

        expected = "LogVer(log_name='simple_repr')\n"
        assert captured == expected

        a_log_name = "simple_repr2_log_name"
        log_ver2 = LogVer(log_name=a_log_name)
        print(log_ver2)  # test of __repr__
        captured = capsys.readouterr().out

        expected = "LogVer(log_name='simple_repr2_log_name')\n"
        assert captured == expected

    ####################################################################
    # test_log_verifier_simple_match
    ####################################################################
    @pytest.mark.parametrize("simple_str_arg", simple_str_arg_list)
    def test_log_verifier_simple_match(
        self,
        simple_str_arg: str,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier time match.

        Args:
            simple_str_arg: string to use in the message
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        t_logger = logging.getLogger("simple_match")
        log_ver = LogVer(log_name="simple_match")

        log_ver.add_msg(log_msg=simple_str_arg)
        t_logger.debug(simple_str_arg)
        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 1 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 1 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('simple_match', 10, '{simple_str_arg}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_print_matched
    ####################################################################
    @pytest.mark.parametrize("print_matched_arg", (None, True, False))
    @pytest.mark.parametrize("num_msgs_arg", (1, 2, 3))
    def test_log_verifier_print_matched(
        self,
        print_matched_arg: Union[bool, None],
        num_msgs_arg: int,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier with print_matched args.

        Args:
            print_matched_arg: specifies whether to print the matched
                records
            num_msgs_arg: number of log messages
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        log_name = "print_matched"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        log_msgs: list[str] = []
        for idx in range(num_msgs_arg):
            log_msgs.append(f"log_msg_{idx}")
            log_ver.add_msg(log_msg=log_msgs[idx])
            t_logger.debug(log_msgs[idx])

        log_results = log_ver.get_match_results(caplog)
        if print_matched_arg is None:
            log_ver.print_match_results(log_results)
        else:
            log_ver.print_match_results(log_results, print_matched=print_matched_arg)
        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += f"* number expected log records: {num_msgs_arg} *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += f"* number actual log records  : {num_msgs_arg} *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += f"* number matched records     : {num_msgs_arg} *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"

        if print_matched_arg is None or print_matched_arg is True:
            expected_result += "\n"
            expected_result += "*********************************\n"
            expected_result += "* matched records               *\n"
            expected_result += "* (logger name, level, message) *\n"
            expected_result += "*********************************\n"

            for log_msg in log_msgs:
                expected_result += f"('{log_name}', 10, '{log_msg}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_simple_fullmatch
    ####################################################################
    double_str_arg_list = [("a1", "a12"), ("b_2", "b_23"), ("xyz_567", "xyz_5678")]

    @pytest.mark.parametrize("double_str_arg", double_str_arg_list)
    def test_log_verifier_simple_fullmatch(
        self,
        double_str_arg: str,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier time match.

        Args:
            double_str_arg: string to use in the message
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        ################################################################
        # step 0: use non-fullmatch in controlled way to cause success
        ################################################################
        log_name = "fullmatch_0"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        log_ver.add_msg(log_msg=double_str_arg[0])
        log_ver.add_msg(log_msg=double_str_arg[1])

        t_logger.debug(double_str_arg[0])
        t_logger.debug(double_str_arg[1])

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 2 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 2 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_0', 10, '{double_str_arg[0]}')\n"
        expected_result += f"('fullmatch_0', 10, '{double_str_arg[1]}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

        ################################################################
        # step 1: use non-fullmatch in controlled way to cause error
        ################################################################
        caplog.clear()

        log_name = "fullmatch_1"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        log_ver.add_msg(log_msg=double_str_arg[0])
        log_ver.add_msg(log_msg=double_str_arg[1])

        t_logger.debug(double_str_arg[1])
        t_logger.debug(double_str_arg[0])

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))

        with pytest.raises(UnmatchedExpectedMessages):
            log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 1 *\n"
        expected_result += "* number actual log records  : 2 *\n"
        expected_result += "* number actual unmatched    : 1 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_1', 10, '{double_str_arg[1]}')\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_1', 10, '{double_str_arg[0]}')\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_1', 10, '{double_str_arg[1]}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

        ################################################################
        # step 2: use fullmatch in controlled way - should succeed
        ################################################################
        caplog.clear()

        log_name = "fullmatch_2"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        log_ver.add_msg(log_msg=double_str_arg[0], fullmatch=True)
        log_ver.add_msg(log_msg=double_str_arg[1], fullmatch=True)

        t_logger.debug(double_str_arg[0])
        t_logger.debug(double_str_arg[1])

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 2 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 2 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_2', 10, '{double_str_arg[0]}')\n"
        expected_result += f"('fullmatch_2', 10, '{double_str_arg[1]}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

        ################################################################
        # step 3: use fullmatch in error case and expect success
        ################################################################
        caplog.clear()

        log_name = "fullmatch_3"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        log_ver.add_msg(log_msg=double_str_arg[0], fullmatch=True)
        log_ver.add_msg(log_msg=double_str_arg[1], fullmatch=True)

        t_logger.debug(double_str_arg[1])
        t_logger.debug(double_str_arg[0])

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))

        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 2 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 2 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_3', 10, '{double_str_arg[1]}')\n"
        expected_result += f"('fullmatch_3', 10, '{double_str_arg[0]}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

        ################################################################
        # step 4: use fullmatch and cause unmatched expected failure
        ################################################################
        caplog.clear()

        log_name = "fullmatch_4"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        log_ver.add_msg(log_msg=double_str_arg[0], fullmatch=True)
        log_ver.add_msg(log_msg=double_str_arg[1], fullmatch=True)

        t_logger.debug(double_str_arg[0])
        # t_logger.debug(double_str_arg[1])

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))

        with pytest.raises(UnmatchedExpectedMessages):
            log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 1 *\n"
        expected_result += "* number actual log records  : 1 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_4', 10, '{double_str_arg[1]}')\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_4', 10, '{double_str_arg[0]}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_same_len_fullmatch
    ####################################################################
    # @pytest.mark.parametrize("msgs_are_same_arg", [True, False])
    # @pytest.mark.parametrize("add_pattern1_first_arg", [True, False])
    # @pytest.mark.parametrize("issue_msg1_first_arg", [True, False])
    # @pytest.mark.parametrize("pattern1_fullmatch_tf_arg", [True, False])
    # @pytest.mark.parametrize("pattern2_fullmatch_tf_arg", [True, False])
    @pytest.mark.parametrize("msgs_are_same_arg", [False, True])
    @pytest.mark.parametrize("add_pattern1_first_arg", [False, True])
    @pytest.mark.parametrize("issue_msg1_first_arg", [False, True])
    @pytest.mark.parametrize("pattern1_fullmatch_tf_arg", [False, True])
    @pytest.mark.parametrize("pattern2_fullmatch_tf_arg", [False, True])
    def test_log_verifier_same_len_fullmatch(
        self,
        msgs_are_same_arg: bool,
        add_pattern1_first_arg: int,
        issue_msg1_first_arg: int,
        pattern1_fullmatch_tf_arg: bool,
        pattern2_fullmatch_tf_arg: bool,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier time match.

        Args:
            msgs_are_same_arg: if True, msg1 is same as msg2
            add_pattern1_first_arg: if 0, pattern1 is issued first
            issue_msg1_first_arg: if 0, msg1 is issued first
            pattern1_fullmatch_tf_arg: if True, use fullmatch for
                pattern1
            pattern2_fullmatch_tf_arg: if True, use fullmatch for
                pattern2
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        # msg diff, p2 1st/match, msg1 1st, p1 match
        ################################################################
        # scenario 00000: diff msgs, p2 1st/match, msg2 1st, p1 match
        #     p2 will find msg2, p1 will find msg1
        # scenario 10000: same msgs, p2 1st/match, msg2 1st, p1 match
        #     p2 will find msg2, p1 will find msg1
        # scenario 01000: diff msgs, p1 1st/match, msg2 1st, p2 match
        #     p1 will find msg1, p2 will find msg2
        # scenario 11000: same msgs, p1 1st/match, msg2 1st, p2 match
        #     p1 will find msg2, p2 will find msg1
        # scenario 00100: diff msgs, p2 1st/match, msg1 1st, p1 match
        #     p2 will find msg1, p1 will *NOT* find msg1 OK ************
        # scenario 10100: same msgs, p2 1st/match, msg1 1st, p1 match
        #     p2 will find msg1, p1 will find msg2
        # scenario 01100: diff msgs, p1 1st/match, msg1 1st, p2 match
        #     p1 will find msg1, p2 will find msg2
        # scenario 11100: same msgs, p1 1st/match, msg1 1st, p2 match
        #     p1 will find msg1, p2 will find msg2

        # scenario 00010: diff msgs, p2 1st/match, msg2 1st, p1 fmatch
        #     p1 will find msg1, p2 will find msg2
        # scenario 10010: same msgs, p2 1st/match, msg2 1st, p1 fmatch
        #     p1 will find msg2, p2 will find msg1
        # scenario 01010: diff msgs, p1 1st/fmatch, msg2 1st, p2 match
        #     p1 will find msg1, p2 will find msg2
        # scenario 11010: same msgs, p1 1st/fmatch, msg2 1st, p2 match
        #     p1 will find msg2, p2 will find msg1
        # scenario 00110: diff msgs, p2 1st/match, msg1 1st, p1 fmatch
        #     p1 will find msg1, p2 will find msg2
        # scenario 10110: same msgs, p2 1st/match, msg1 1st, p1 fmatch
        #     p1 will find msg1, p2 will find msg2
        # scenario 01110: diff msgs, p1 1st/fmatch, msg1 1st, p2 match
        #     p1 will find msg1, p2 will find msg2
        # scenario 11110: same msgs, p1 1st/fmatch, msg1 1st, p2 match
        #     p1 will find msg1, p2 will find msg2

        # msg diff, p2 1st/fmatch, msg1 1st, p1 match
        # msg diff, p1 1st/match, msg1 1st, p2 fmatch
        # scenario 00001: diff msgs, p2 1st/fmatch, msg2 1st, p1 match
        #     p2 will find msg2, p1 will find msg1
        # scenario 10001: same msgs, p2 1st/fmatch, msg2 1st, p1 match
        #     p2 will find msg2, p1 will find msg1
        # scenario 01001: diff msgs, p1 1st/match, msg2 1st, p2 fmatch
        #     p2 will find msg2, p1 will find msg1
        # scenario 11001: same msgs, p1 1st/match, msg2 1st, p2 fmatch
        #     p2 will find msg2, p1 will find msg1
        # scenario 00101: diff msgs, p2 1st/fmatch, msg1 1st, p1 match
        #     p2 will find msg1, p1 will *NOT* find msg1 OK ************
        # scenario 10101: same msgs, p2 1st/fmatch, msg1 1st, p1 match
        #     p2 will find msg1, p1 will find msg2
        # scenario 01101: diff msgs, p1 1st/match, msg1 1st, p2 fmatch
        #     p2 will find msg1, p1 will *NOT* find msg2 OK ************
        # scenario 11101: same msgs, p1 1st/match, msg1 1st, p2 fmatch
        #     p2 will find msg1, p1 will find msg2

        # msg diff, p2 1st/fmatch, msg1 1st, p1 fmatch
        # scenario 00011: diff msgs, p2 1st/fmatch, msg2 1st, p1 fmatch
        #     p2 will find msg2, p1 will find msg1
        # scenario 10011: same msgs, p2 1st/fmatch, msg2 1st, p1 fmatch
        #     p2 will find msg2, p1 will find msg1
        # scenario 01011: diff msgs, p1 1st/fmatch, msg2 1st, p2 fmatch
        #     p1 will find msg1, p2 will find msg2
        # scenario 11011: same msgs, p1 1st/fmatch, msg2 1st, p2 fmatch
        #     p1 will find msg2, p2 will find msg1
        # scenario 00111: diff msgs, p2 1st/fmatch, msg1 1st, p1 fmatch
        #     p2 will find msg1, p1 will *NOT* find msg2 OK ************
        # scenario 10111: same msgs, p2 1st/fmatch, msg1 1st, p1 fmatch
        #     p2 will find msg1, p1 will find msg2
        # scenario 01111: diff msgs, p1 1st/fmatch, msg1 1st, p2 fmatch
        #     p1 will find msg1, p2 will find msg2
        # scenario 11111: same msgs, p1 1st/fmatch, msg1 1st, p2 fmatch
        #     p1 will find msg1, p2 will find msg2
        #
        #
        #
        ################################################################
        ################################################################
        # build msgs
        ################################################################
        # num_per_section = 4
        # remaining_first_chars = (
        #     num_per_section - num_first_chars_same_arg + num_per_section
        # )
        # remaining_mid_chars = num_per_section - num_mid_chars_same_arg + num_per_section
        # remaining_last_chars = (
        #     num_per_section - num_last_chars_same_arg + num_per_section
        # )
        # msg1 = (
        #     string.printable[0:num_per_section]
        #     + "_"
        #     + string.printable[0:num_per_section]
        #     + "_"
        #     + string.printable[0:num_per_section]
        # )
        # msg2 = (
        #     string.printable[0:num_first_chars_same_arg]
        #     + string.printable[num_per_section:remaining_first_chars]
        #     + "_"
        #     + string.printable[0:num_mid_chars_same_arg]
        #     + string.printable[num_per_section:remaining_mid_chars]
        #     + "_"
        #     + string.printable[0:num_last_chars_same_arg]
        #     + string.printable[num_per_section:remaining_last_chars]
        # )
        print(f"\n{msgs_are_same_arg=}")
        print(f"\n{add_pattern1_first_arg=}")
        print(f"\n{issue_msg1_first_arg=}")
        print(f"\n{pattern1_fullmatch_tf_arg=}")
        print(f"\n{pattern2_fullmatch_tf_arg=}")

        msg1 = "abc_123"
        if msgs_are_same_arg:
            msg2 = msg1
        else:
            msg2 = "abc_321"
        ################################################################
        # build patterns
        ################################################################

        pattern1 = msg1

        pattern2 = "abc_[0-9]{3}"

        first_found = ""
        exp_error = False
        if msgs_are_same_arg:
            if issue_msg1_first_arg:
                first_found = msg1
            else:  # msg2 issued first
                first_found = msg2
        else:  # msgs differ
            if add_pattern1_first_arg:
                if issue_msg1_first_arg:
                    first_found = msg1
                    if not pattern1_fullmatch_tf_arg and pattern2_fullmatch_tf_arg:
                        exp_error = True
                else:  # msg2 issued first
                    if pattern1_fullmatch_tf_arg and not pattern2_fullmatch_tf_arg:
                        first_found = msg1
                    else:
                        first_found = msg2
            else:  # pattern2 goes first
                if issue_msg1_first_arg:
                    first_found = msg1
                    if not pattern1_fullmatch_tf_arg or pattern2_fullmatch_tf_arg:
                        exp_error = True
                else:  # msg2 issued first
                    if pattern1_fullmatch_tf_arg and not pattern2_fullmatch_tf_arg:
                        first_found = msg1
                    else:
                        first_found = msg2

        ################################################################
        # add patterns and issue log msgs
        ################################################################
        caplog.clear()

        log_name = "fullmatch_0"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        if add_pattern1_first_arg:
            log_ver.add_msg(log_msg=pattern1, fullmatch=pattern1_fullmatch_tf_arg)
            log_ver.add_msg(log_msg=pattern2, fullmatch=pattern2_fullmatch_tf_arg)
        else:
            log_ver.add_msg(log_msg=pattern2, fullmatch=pattern2_fullmatch_tf_arg)
            log_ver.add_msg(log_msg=pattern1, fullmatch=pattern1_fullmatch_tf_arg)

        if issue_msg1_first_arg:
            t_logger.debug(msg1)
            t_logger.debug(msg2)
        else:
            t_logger.debug(msg2)
            t_logger.debug(msg1)

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))

        if exp_error:
            with pytest.raises(UnmatchedExpectedMessages):
                log_ver.verify_log_results(log_results)
        else:
            log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += f"{msgs_are_same_arg=}\n\n"
        expected_result += f"{add_pattern1_first_arg=}\n\n"
        expected_result += f"{issue_msg1_first_arg=}\n\n"
        expected_result += f"{pattern1_fullmatch_tf_arg=}\n\n"
        expected_result += f"{pattern2_fullmatch_tf_arg=}\n"

        expected_result += "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"

        if exp_error:
            expected_result += "* number expected unmatched  : 1 *\n"
        else:
            expected_result += "* number expected unmatched  : 0 *\n"

        expected_result += "* number actual log records  : 2 *\n"

        if exp_error:
            expected_result += "* number actual unmatched    : 1 *\n"
            expected_result += "* number matched records     : 1 *\n"
        else:
            expected_result += "* number actual unmatched    : 0 *\n"
            expected_result += "* number matched records     : 2 *\n"

        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        if exp_error:
            expected_result += f"('fullmatch_0', 10, '{pattern1}')\n"

        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        if exp_error:
            expected_result += f"('fullmatch_0', 10, '{msg2}')\n"

        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        # if issue_msg1_first_arg:
        #     expected_result += f"('fullmatch_0', 10, '{msg1}')\n"
        #     expected_result += f"('fullmatch_0', 10, '{msg2}')\n"
        # else:
        #     expected_result += f"('fullmatch_0', 10, '{msg2}')\n"
        #     expected_result += f"('fullmatch_0', 10, '{msg1}')\n"
        if first_found == msg1:
            expected_result += f"('fullmatch_0', 10, '{msg1}')\n"
            if not exp_error:
                expected_result += f"('fullmatch_0', 10, '{msg2}')\n"
        else:
            expected_result += f"('fullmatch_0', 10, '{msg2}')\n"
            expected_result += f"('fullmatch_0', 10, '{msg1}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_same_len_fullmatch
    ####################################################################
    # @pytest.mark.parametrize("num_patterns_arg", [0, 1, 2, 3])
    # @pytest.mark.parametrize("num_msgs_arg", [0, 1, 2, 3])
    # msg_combos = mi.collapse(
    #     map(lambda n: it.product(("msg1", "msg2", "msg3")[0:n], repeat=n), range(4)),
    #     base_type=tuple,
    # )
    msgs = ["msg1", "msg2", "msg3"]
    msg_perms = it.permutations(msgs, 3)
    msg_combos = mi.collapse(
        map(
            lambda mp: map(lambda n: it.product(mp[0:n], repeat=n), range(4)), msg_perms
        ),
        base_type=tuple,
    )
    msg_combos_list = sorted(set(msg_combos), key=lambda x: (len(x), x))

    patterns = (
        # "msg0",
        # "msg1",
        # "msg2",
        # "msg3",
        # "msg[12]{1}",
        "msg[13]{1}",
        "msg[23]{1}",
        "msg[123]{1}",
    )

    pattern_3_combos = it.combinations(patterns, 3)
    pattern_perms = mi.collapse(
        map(lambda p3: it.permutations(p3, 3), pattern_3_combos), base_type=tuple
    )

    pattern_combos = mi.collapse(
        map(
            lambda mp: map(lambda n: it.product(mp[0:n], repeat=n), range(4)),
            pattern_perms,
        ),
        base_type=tuple,
    )
    pattern_combos_list = sorted(set(pattern_combos), key=lambda x: (len(x), x))

    @pytest.mark.parametrize("msgs_arg", msg_combos_list)
    @pytest.mark.parametrize("patterns_arg", pattern_combos_list)
    def test_log_verifier_contention(
        self,
        msgs_arg: Iterable[tuple[str]],
        patterns_arg: Iterable[tuple[str]],
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier time match.

        Args:
            msgs_arg: tuple of log msgs to issue
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        print(f"\n{msgs_arg=}, \n{patterns_arg=}")
        matched_msg_array: dict[str, set[str]] = {
            "msg0": {""},
            "msg1": {"msg1"},
            "msg2": {"msg2"},
            "msg3": {"msg3"},
            "msg[12]{1}": {"msg1", "msg2"},
            "msg[13]{1}": {"msg1", "msg3"},
            "msg[23]{1}": {"msg2", "msg3"},
            "msg[123]{1}": {"msg1", "msg2", "msg3"},
        }

        matched_pattern_array: dict[str, set[str]] = {
            "msg1": {"msg1", "msg[12]{1}", "msg[13]{1}", "msg[123]{1}"},
            "msg2": {"msg2", "msg[12]{1}", "msg[23]{1}", "msg[123]{1}"},
            "msg3": {"msg3", "msg[13]{1}", "msg[23]{1}", "msg[123]{1}"},
        }

        if msgs_arg:
            msgs_arg_set = set(msgs_arg)
            msgs_arg_list = list(msgs_arg)
        else:
            msgs_arg_set = {""}
            msgs_arg_list = []

        if patterns_arg:
            patterns_arg_set = set(patterns_arg)
            patterns_arg_list = list(patterns_arg)
        else:
            patterns_arg_set = {""}
            patterns_arg_list = []

        sort_x_y_x_msg = ""
        if len(msgs_arg_list) == 3:
            for msg in msgs_arg_list:
                if msgs_arg_list.count(msg) > 1 and msg == msgs_arg_list[2]:
                    sort_x_y_x_msg = msg
                    break

        sort_x_y_x_pattern = ""
        if len(patterns_arg_list) == 3:
            for pattern in patterns_arg_list:
                if (
                    patterns_arg_list.count(pattern) > 1
                    and pattern == patterns_arg_list[2]
                ):
                    sort_x_y_x_pattern = pattern
                    break

        def sort_items(items: list[str], ref_list: list[str], sort_x_y_item: str):
            x_y_z_item_found = False

            def sort_rtn(item):
                nonlocal x_y_z_item_found
                if item == sort_x_y_item:
                    if x_y_z_item_found:
                        return 3
                    else:
                        x_y_z_item_found = True
                return ref_list.index(item)

            items.sort(key=sort_rtn)
            return items

        def filter_potential_msgs(potential_msgs, filter_msgs, sort_x_y_item):
            # x_y_z_item_found = False
            #
            # def sort_rtn(item):
            #     nonlocal x_y_z_item_found
            #     if item == sort_x_y_item:
            #         if x_y_z_item_found:
            #             return 3
            #         else:
            #             x_y_z_item_found = True
            #     return filter_msgs.index(item)

            ret_list = list(potential_msgs & set(filter_msgs))
            return sort_items(ret_list, filter_msgs, sort_x_y_item)
            # ret_list.sort(key=sort_rtn)
            # return ret_list

        unmatched_patterns: list[str] = []
        unmatched_msgs: list[str] = []
        matched_msgs: list[str] = []

        pattern_df = pd.DataFrame()
        msg_df = pd.DataFrame()

        ################################################################
        # create pandas array for patterns
        ################################################################
        if patterns_arg:
            pattern_df = pd.DataFrame(patterns_arg, columns=["pattern"])

            pattern_df["potential_msgs"] = pattern_df["pattern"].map(matched_msg_array)
            pattern_df["potential_msgs"] = pattern_df["potential_msgs"].apply(
                filter_potential_msgs,
                filter_msgs=msgs_arg_list,
                sort_x_y_item=sort_x_y_x_msg,
            )
            pattern_df["claimed_msg"] = "none"

        if msgs_arg:
            msg_df = pd.DataFrame(msgs_arg, columns=["msg"])
            msg_df["potential_patterns"] = msg_df["msg"].map(matched_pattern_array)
            msg_df["potential_patterns"] = msg_df["potential_patterns"].apply(
                filter_potential_msgs,
                filter_msgs=patterns_arg_list,
                sort_x_y_item=sort_x_y_x_pattern,
            )

            msg_df["claimed_pattern"] = "none"

        num_found_all_msgs = 0
        test_matched_found_msgs_list = []
        test_unmatched_found_msgs_list = []
        test_not_found_msgs_list = []
        no_match_patterns = []
        no_match_msgs = []
        if patterns_arg and msgs_arg:
            ############################################################
            # handle patterns with 1 potential msg
            ############################################################
            for idx in range(len(pattern_df)):
                pattern = pattern_df["pattern"].iloc[idx]
                if len(pattern_df["potential_msgs"].iloc[idx]) == 0:
                    no_match_patterns.append(pattern)
                if len(pattern_df["potential_msgs"].iloc[idx]) == 1:
                    for p_msg in pattern_df["potential_msgs"].iloc[idx]:
                        for idx2 in range(len(msg_df)):
                            if (
                                p_msg == msg_df["msg"].iloc[idx2]
                                and msg_df["claimed_pattern"].iloc[idx2] == "none"
                            ):
                                pattern_df["claimed_msg"].iloc[idx] = p_msg
                                msg_df["claimed_pattern"].iloc[idx2] = pattern
                                break
                        if pattern_df["claimed_msg"].iloc[idx] != "none":
                            break

            ############################################################
            # handle msgs with 1 potential pattern
            ############################################################
            for idx in range(len(msg_df)):
                if msg_df["claimed_pattern"].iloc[idx] == "none":
                    msg = msg_df["msg"].iloc[idx]
                    if len(msg_df["potential_patterns"].iloc[idx]) == 0:
                        no_match_msgs.append(msg)
                    if len(msg_df["potential_patterns"].iloc[idx]) == 1:
                        for p_pattern in msg_df["potential_patterns"].iloc[idx]:
                            for idx2 in range(len(pattern_df)):
                                if (
                                    p_pattern == pattern_df["pattern"].iloc[idx2]
                                    and pattern_df["claimed_msg"].iloc[idx2] == "none"
                                ):
                                    msg_df["claimed_pattern"].iloc[idx] = p_pattern
                                    pattern_df["claimed_msg"].iloc[idx2] = msg
                                    break
                            if msg_df["claimed_pattern"].iloc[idx] != "none":
                                break

            ############################################################
            # handle patterns with 2 potential msgs
            ############################################################
            for idx in range(len(pattern_df)):
                if pattern_df["claimed_msg"].iloc[idx] == "none":
                    pattern = pattern_df["pattern"].iloc[idx]
                    if len(pattern_df["potential_msgs"].iloc[idx]) == 2:
                        for p_msg in pattern_df["potential_msgs"].iloc[idx]:
                            for idx2 in range(len(msg_df)):
                                if (
                                    p_msg == msg_df["msg"].iloc[idx2]
                                    and msg_df["claimed_pattern"].iloc[idx2] == "none"
                                ):
                                    pattern_df["claimed_msg"].iloc[idx] = p_msg
                                    msg_df["claimed_pattern"].iloc[idx2] = pattern
                                    break
                            if pattern_df["claimed_msg"].iloc[idx] != "none":
                                break

            ############################################################
            # handle msgs with 2 potential pattern
            ############################################################
            for idx in range(len(msg_df)):
                if msg_df["claimed_pattern"].iloc[idx] == "none":
                    msg = msg_df["msg"].iloc[idx]
                    if len(msg_df["potential_patterns"].iloc[idx]) == 2:
                        for p_pattern in msg_df["potential_patterns"].iloc[idx]:
                            for idx2 in range(len(pattern_df)):
                                if (
                                    p_pattern == pattern_df["pattern"].iloc[idx2]
                                    and pattern_df["claimed_msg"].iloc[idx2] == "none"
                                ):
                                    msg_df["claimed_pattern"].iloc[idx] = p_pattern
                                    pattern_df["claimed_msg"].iloc[idx2] = msg
                                    break
                            if msg_df["claimed_pattern"].iloc[idx] != "none":
                                break

            ############################################################
            # complete patterns with unclaimed msgs
            ############################################################
            for idx in range(len(pattern_df)):
                if pattern_df["claimed_msg"].iloc[idx] == "none":
                    pattern = pattern_df["pattern"].iloc[idx]
                    for p_msg in pattern_df["potential_msgs"].iloc[idx]:
                        for idx2 in range(len(msg_df)):
                            if (
                                p_msg == msg_df["msg"].iloc[idx2]
                                and msg_df["claimed_pattern"].iloc[idx2] == "none"
                            ):
                                pattern_df["claimed_msg"].iloc[idx] = p_msg
                                msg_df["claimed_pattern"].iloc[idx2] = pattern
                                break
                        if pattern_df["claimed_msg"].iloc[idx] != "none":
                            break

            for perm_idx in it.permutations(range(len(pattern_df))):
                msg_combo_lists = []
                for idx in perm_idx:
                    if len(pattern_df["potential_msgs"].iloc[idx]) > 0:
                        msg_combo_lists.append(pattern_df["potential_msgs"].iloc[idx])
                    else:
                        msg_combo_lists.append(["none"])
                msg_prods = ""
                if len(msg_combo_lists) == 1:
                    msg_prods = it.product(
                        msg_combo_lists[0],
                    )
                elif len(msg_combo_lists) == 2:
                    msg_prods = it.product(
                        msg_combo_lists[0],
                        msg_combo_lists[1],
                    )
                elif len(msg_combo_lists) == 3:
                    msg_prods = it.product(
                        msg_combo_lists[0],
                        msg_combo_lists[1],
                        msg_combo_lists[2],
                    )
                msg_prods = list(msg_prods)
                print(f"{msg_prods=}")
                for msg_prod in msg_prods:
                    test_found_msgs = []
                    msgs_arg_copy = msgs_arg_list.copy()
                    for msg in msg_prod:
                        if msg in msgs_arg_copy:
                            test_found_msgs.append(msg)
                            msgs_arg_copy.remove(msg)
                    # test_found_msgs.sort(key=msgs_arg.index)
                    test_found_msgs = sort_items(
                        test_found_msgs,
                        msgs_arg_list,
                        sort_x_y_x_msg,
                    )
                    msgs_arg_copy = sort_items(
                        msgs_arg_copy,
                        msgs_arg_list,
                        sort_x_y_x_msg,
                    )
                    test_matched_found_msgs_list.append(test_found_msgs)
                    test_unmatched_found_msgs_list.append(msgs_arg_copy.copy())

                # print(f"{test_matched_found_msgs_list=}")
                # matched_found_msgs = []
                # unmatched_found_msgs = []
                # for found_msgs in test_matched_found_msgs_list:
                #     for idx, msg in enumerate(found_msgs):
                #         if msg == msgs_arg_list[idx]:
                #             matched_found_msgs.append(msg)
                #         else:
                #             unmatched_found_msgs.append(msgs_arg_list[idx])
                #
                #     if found_msgs == msgs_arg_list:
                #         num_found_all_msgs += 1
                #     else:
                #         for idx, msg in enumerate(found_msgs):
                #             if
                #         test_not_found_msgs_list.append(found_msgs)

            # print(
            #     f"{msgs_arg_list=} \n{num_found_all_msgs=}, \n   "
            #     f" {test_not_found_msgs_list=}"
            # )

        for idx in range(len(pattern_df)):
            pattern = pattern_df["pattern"].iloc[idx]
            if pattern_df["claimed_msg"].iloc[idx] == "none":
                unmatched_patterns.append(pattern)

        for idx in range(len(msg_df)):
            msg = msg_df["msg"].iloc[idx]
            if msg_df["claimed_pattern"].iloc[idx] == "none":
                unmatched_msgs.append(msg)
            else:
                matched_msgs.append(msg)

        unmatched_msgs = sort_items(unmatched_msgs, msgs_arg_list, sort_x_y_x_msg)
        matched_msgs = sort_items(matched_msgs, msgs_arg_list, sort_x_y_x_msg)

        num_unmatched_agreed = 0
        num_unmatched_not_agreed = 0
        if patterns_arg_list and msgs_arg_list:
            for test_unmatched_found_msgs in test_unmatched_found_msgs_list:
                if test_unmatched_found_msgs == unmatched_msgs:
                    num_unmatched_agreed += 1
                else:
                    num_unmatched_not_agreed += 1
        else:
            if not matched_msgs and unmatched_msgs == msgs_arg_list:
                num_unmatched_agreed = 1

        num_matched_agreed = 0
        num_matched_not_agreed = 0
        if patterns_arg_list and msgs_arg_list:
            for test_matched_found_msgs in test_matched_found_msgs_list:
                if test_matched_found_msgs == matched_msgs:
                    num_matched_agreed += 1
        else:
            if not matched_msgs and unmatched_msgs == msgs_arg_list:
                num_matched_agreed = 1

        print(f"\npattern_df: \n{pattern_df}")
        print(f"\nmsg_df: \n{msg_df}")
        print(f"{unmatched_patterns=}")
        print(f"{unmatched_msgs=}")
        print(f"{matched_msgs=}")

        print(f"{num_unmatched_agreed=}")
        print(f"{num_unmatched_not_agreed=}")

        print(f"{num_matched_agreed=}")
        print(f"{num_matched_not_agreed=}")

        assert num_unmatched_agreed
        assert num_matched_agreed

        # do_assert = True
        # for idx in range(len(pattern_df)):
        #     if not pattern_df["potential_msgs"].iloc[idx]:
        #         do_assert = False
        #
        # avail_msgs = list(msgs_arg)
        # for idx in range(len(pattern_df)):
        #     potential_msgs = list(pattern_df["potential_msgs"].iloc[idx])
        #     if len(potential_msgs) == 1:
        #         p_msg = potential_msgs[0]
        #         if p_msg in avail_msgs:
        #             avail_msgs.remove(p_msg)
        #         else:
        #             do_assert = False
        #
        # for idx in range(len(msg_df)):
        #     if not msg_df["potential_patterns"].iloc[idx]:
        #         do_assert = False
        #
        # if do_assert and len(pattern_df) == len(msg_df):
        #     assert not unmatched_patterns
        #     assert not unmatched_msgs
        #
        # if (
        #     (len(patterns_arg_list) > 0)
        #     and (len(patterns_arg_list) == len(msgs_arg_list))
        #     and not no_match_patterns
        #     and not no_match_msgs
        # ):
        #     assert num_found_all_msgs
        ################################################################
        # log msgs: msg1, msg2, msg3
        # patterns: msg0: no match
        #           msg1: matches msg1
        #           msg2: matches msg2
        #           msg3: matches msg3
        #           msg[12]{1}: matches both msg1 and msg2
        #           msg[23]{1}: matches both msg1 and msg3
        #           msg[123]{1}: matches msg1, msg2, and msg3

        # scenario 0, 0: 0 patterns, 0 msgs
        #   msgs: n/a
        #     patterns: n/a
        #       0 unmatched patterns
        #       0 unmatched msgs
        #       0 matched msgs

        # scenario 0, 1: 0 patterns, 1 msgs
        #   msgs: msg1
        #     patterns: n/a
        #       0 unmatched patterns
        #       1 unmatched msg: msg1
        #       0 matched msgs

        # scenario 0, 2: 0 patterns, 2 msgs
        #   msgs: msg1, msg1
        #     patterns: n/a
        #       0 unmatched patterns
        #       2 unmatched msgs: msg1, msg1
        #       0 matched msgs
        #   msgs: msg1, msg2
        #     patterns: n/a
        #       0 unmatched patterns
        #       2 unmatched msgs: msg1, msg2
        #       0 matched msgs
        #   msgs: msg2, msg1
        #     patterns: n/a
        #       0 unmatched patterns
        #       2 unmatched msgs: msg2, msg1
        #       0 matched msgs
        #   msgs: msg2, msg2
        #     patterns: n/a
        #       0 unmatched patterns
        #       2 unmatched msgs: msg2, msg2
        #       0 matched msgs

        # scenario 0, 3: 0 patterns, 3 msgs
        #   msgs: msg1, msg1, msg1
        #     patterns: n/a
        #       0 unmatched patterns
        #       3 unmatched msgs: msg1, msg1, msg1
        #       0 matched msgs
        #   msgs: msg1, msg1, msg2
        #     patterns: n/a
        #       0 unmatched patterns
        #       3 unmatched msgs: msg1, msg1, msg2
        #       0 matched msgs
        #   msgs: msg1, msg1, msg3
        #     patterns: n/a
        #       0 unmatched patterns
        #       3 unmatched msgs: msg1, msg1, msg3
        #       0 matched msgs
        #   msgs: msg1, msg2, msg1
        #     patterns: n/a
        #       0 unmatched patterns
        #       3 unmatched msgs: msg1, msg2, msg1
        #       0 matched msgs
        #   msgs: msg1, msg2, msg2
        #     patterns: n/a
        #       0 unmatched patterns
        #       3 unmatched msgs: msg1, msg2, msg2
        #       0 matched msgs
        #   msgs: msg1, msg2, msg3
        #     patterns: n/a
        #       0 unmatched patterns
        #       3 unmatched msgs: msg1, msg2, msg3
        #       0 matched msgs
        #   msgs: msg1, msg3, msg1
        #     patterns: n/a
        #       0 unmatched patterns
        #       3 unmatched msgs: msg1, msg3, msg1
        #       0 matched msgs
        #   msgs: msg1, msg3, msg2
        #     patterns: n/a
        #       0 unmatched patterns
        #       3 unmatched msgs: msg1, msg3, msg2
        #       0 matched msgs
        #   msgs: msg1, msg3, msg3
        #     patterns: n/a
        #       0 unmatched patterns
        #       3 unmatched msgs: msg1, msg3, msg3
        #       0 matched msgs
        #   msgs: msg2, msg1, msg1
        #     patterns: n/a
        #       0 unmatched patterns
        #       3 unmatched msgs: msg2, msg1, msg1
        #       0 matched msgs
        #   etc,

        # scenario 1, 0: 1 patterns, 0 msgs
        #   msgs: n/a
        #     patterns: msg0
        #       1 unmatched pattern msg0
        #       0 unmatched msgs
        #       0 matched msgs

        # scenario 1, 1: 1 patterns, 1 msgs
        #   msgs: msg1
        #     patterns: msg0

        #       1 unmatched patterns: msg0
        #       1 unmatched msgs: msg1
        #       0 matched msgs
        #     patterns: msg1
        #       0 unmatched patterns
        #       0 unmatched msgs
        #       1 matched msgs: msg1

        # scenario 1, 2: 1 patterns, 2 msgs
        #   msgs: msg1, msg2
        #     patterns: msg0
        #       1 unmatched patterns: msg0
        #       2 unmatched msgs: msg1, msg2
        #       0 matched msgs
        #     patterns: msg1
        #       0 unmatched patterns
        #       1 unmatched msgs: msg2
        #       1 matched msgs: msg1
        #     patterns: msg2
        #       0 unmatched patterns
        #       1 unmatched msgs: msg1
        #       1 matched msgs: msg2
        #     patterns: msg[12]{1}
        #       0 unmatched patterns
        #       1 unmatched msgs: msg2
        #       1 matched msg1

        # scenario 1, 3: 1 patterns, 3 msgs
        #   msgs: msg1, msg2, msg3
        #     patterns: msg0
        #       1 unmatched patterns: msg0
        #       3 unmatched msgs: msg1, msg2, msg3
        #       0 matched msgs
        #     patterns: msg1
        #       0 unmatched patterns
        #       2 unmatched msgs: msg2, msg3
        #       1 matched msgs: msg1
        #     patterns: msg2
        #       0 unmatched patterns
        #       2 unmatched msgs: msg1, msg3
        #       1 matched msgs: msg2
        #     patterns: msg3
        #       0 unmatched patterns
        #       2 unmatched msgs: msg1, msg2
        #       1 matched msgs: msg3
        #     patterns: msg[12]{1}
        #       0 unmatched patterns
        #       2 unmatched msgs: msg2, msg3
        #       1 matched msg1
        #     patterns: msg[13]{1}
        #       0 unmatched patterns
        #       2 unmatched msgs: msg2, msg3
        #       1 matched msg1
        #     patterns: msg[23]{1}
        #       0 unmatched patterns
        #       2 unmatched msgs: msg1, msg3
        #       1 matched msg2
        #     patterns: msg[123]{1}
        #       0 unmatched patterns
        #       2 unmatched msgs: msg2, msg3
        #       1 matched msg1

        # scenario 2, 0: 2 patterns, 0 msgs
        #   msgs: n/a
        #     patterns: msg0, msg0
        #       2 unmatched patterns: msg0, msg0
        #       0 unmatched msgs:
        #       0 matched msgs

        # scenario 2, 1: 2 patterns, 1 msgs
        #   msgs: msg1
        #     patterns: msg0, msg0
        #       2 unmatched patterns: msg0, msg0
        #       1 unmatched msgs: msg1
        #       0 matched msgs
        #     patterns: msg0, msg1
        #       1 unmatched patterns: msg0
        #       0 unmatched msgs:
        #       1 matched msgs: msg1
        #     patterns: msg1, msg0
        #       1 unmatched patterns: msg0
        #       0 unmatched msgs:
        #       1 matched msgs: msg1
        #     patterns: msg1, msg1
        #       1 unmatched patterns: msg1
        #       0 unmatched msgs:
        #       1 matched msgs: msg1

        # scenario 2, 2: 2 patterns, 2 msgs
        #   msgs: msg1, msg2
        #     patterns: msg0, msg0
        #       2 unmatched patterns: msg0, msg0
        #       2 unmatched msgs: msg1, msg2
        #       0 matched msgs
        #     patterns: msg0, msg1
        #       1 unmatched patterns: msg0
        #       1 unmatched msgs: msg2
        #       1 matched msgs: msg1
        #     patterns: msg0, msg2
        #       1 unmatched patterns: msg0
        #       1 unmatched msgs: msg1
        #       1 matched msgs: msg2
        #     patterns: msg0, msg[12]{1}
        #       1 unmatched patterns: msg0
        #       1 unmatched msgs: msg2
        #       1 matched msgs: msg1
        #     patterns: msg1, msg0
        #       1 unmatched patterns: msg0
        #       1 unmatched msgs: msg2
        #       1 matched msgs: msg1
        #     patterns: msg1, msg1
        #       1 unmatched patterns: msg1
        #       1 unmatched msgs: msg2
        #       1 matched msgs: msg1
        #     patterns: msg1, msg2
        #       0 unmatched patterns:
        #       0 unmatched msgs:
        #       2 matched msgs: msg1, msg2
        #     patterns: msg1, msg[12]{1}
        #       0 unmatched patterns:
        #       0 unmatched msgs:
        #       2 matched msgs: msg1, msg2
        #     patterns: msg2, msg0
        #       1 unmatched patterns: msg0
        #       1 unmatched msgs: msg1
        #       1 matched msgs: msg2
        #     patterns: msg2, msg1
        #       0 unmatched patterns:
        #       0 unmatched msgs:
        #       2 matched msgs: msg1, msg2
        #     patterns: msg2, msg2
        #       1 unmatched patterns: msg2
        #       1 unmatched msgs: msg1
        #       1 matched msgs: msg2
        #     patterns: msg2, msg[12]{1}
        #       0 unmatched patterns:
        #       0 unmatched msgs:
        #       2 matched msgs: msg1, msg2
        #     patterns: msg[12]{1}, msg0
        #       1 unmatched patterns: msg0
        #       1 unmatched msgs: msg2
        #       1 matched msgs: msg1
        #     patterns: msg[12]{1}, msg1
        #       0 unmatched patterns:
        #       0 unmatched msgs:
        #       2 matched msgs: msg1, msg2
        #     patterns: msg[12]{1}, msg2
        #       0 unmatched patterns:
        #       0 unmatched msgs:
        #       2 matched msgs: msg1, msg2
        #     patterns: msg[12]{1}, msg[12]{1}
        #       0 unmatched patterns:
        #       0 unmatched msgs:
        #       2 matched msgs: msg1, msg2

        # scenario 2, 3: 2 patterns, 3 msgs
        #     0 unmatched patterns, 1 unmatched msgs, 2 matched msgs

        # scenario 3, 0: 2 patterns, 0 msgs
        #     3 unmatched patterns, 0 unmatched msgs, 0 matched msgs
        # scenario 3, 1: 2 patterns, 1 msgs
        #     2 unmatched patterns, 0 unmatched msgs, 1 matched msgs
        # scenario 3, 2: 2 patterns, 2 msgs
        #     1 unmatched patterns, 0 unmatched msgs, 2 matched msgs
        # scenario 3, 3: 2 patterns, 3 msgs
        #     0 unmatched patterns, 0 unmatched msgs, 3 matched msgs

        ################################################################
        ################################################################
        # build msgs
        ################################################################
        # num_per_section = 4
        # remaining_first_chars = (
        #     num_per_section - num_first_chars_same_arg + num_per_section
        # )
        # remaining_mid_chars = num_per_section - num_mid_chars_same_arg + num_per_section
        # remaining_last_chars = (
        #     num_per_section - num_last_chars_same_arg + num_per_section
        # )
        # msg1 = (
        #     string.printable[0:num_per_section]
        #     + "_"
        #     + string.printable[0:num_per_section]
        #     + "_"
        #     + string.printable[0:num_per_section]
        # )
        # msg2 = (
        #     string.printable[0:num_first_chars_same_arg]
        #     + string.printable[num_per_section:remaining_first_chars]
        #     + "_"
        #     + string.printable[0:num_mid_chars_same_arg]
        #     + string.printable[num_per_section:remaining_mid_chars]
        #     + "_"
        #     + string.printable[0:num_last_chars_same_arg]
        #     + string.printable[num_per_section:remaining_last_chars]
        # )
        # print(f"\n{msgs_are_same_arg=}")
        # print(f"\n{add_pattern1_first_arg=}")
        # print(f"\n{issue_msg1_first_arg=}")
        # print(f"\n{pattern1_fullmatch_tf_arg=}")
        # print(f"\n{pattern2_fullmatch_tf_arg=}")

        # msg1 = "abc_123"
        # if msgs_are_same_arg:
        #     msg2 = msg1
        # else:
        #     msg2 = "abc_321"
        # ################################################################
        # # build patterns
        # ################################################################
        #
        # pattern1 = msg1
        #
        # pattern2 = "abc_[0-9]{3}"
        #
        # first_found = ""
        # exp_error = False
        # if msgs_are_same_arg:
        #     if issue_msg1_first_arg:
        #         first_found = msg1
        #     else:  # msg2 issued first
        #         first_found = msg2
        # else:  # msgs differ
        #     if add_pattern1_first_arg:
        #         if issue_msg1_first_arg:
        #             first_found = msg1
        #             if not pattern1_fullmatch_tf_arg and pattern2_fullmatch_tf_arg:
        #                 exp_error = True
        #         else:  # msg2 issued first
        #             if pattern1_fullmatch_tf_arg and not pattern2_fullmatch_tf_arg:
        #                 first_found = msg1
        #             else:
        #                 first_found = msg2
        #     else:  # pattern2 goes first
        #         if issue_msg1_first_arg:
        #             first_found = msg1
        #             if not pattern1_fullmatch_tf_arg or pattern2_fullmatch_tf_arg:
        #                 exp_error = True
        #         else:  # msg2 issued first
        #             if pattern1_fullmatch_tf_arg and not pattern2_fullmatch_tf_arg:
        #                 first_found = msg1
        #             else:
        #                 first_found = msg2
        #
        # ################################################################
        # # add patterns and issue log msgs
        # ################################################################
        # caplog.clear()
        #
        # log_name = "fullmatch_0"
        # t_logger = logging.getLogger(log_name)
        # log_ver = LogVer(log_name=log_name)
        #
        # if add_pattern1_first_arg:
        #     log_ver.add_msg(log_msg=pattern1, fullmatch=pattern1_fullmatch_tf_arg)
        #     log_ver.add_msg(log_msg=pattern2, fullmatch=pattern2_fullmatch_tf_arg)
        # else:
        #     log_ver.add_msg(log_msg=pattern2, fullmatch=pattern2_fullmatch_tf_arg)
        #     log_ver.add_msg(log_msg=pattern1, fullmatch=pattern1_fullmatch_tf_arg)
        #
        # if issue_msg1_first_arg:
        #     t_logger.debug(msg1)
        #     t_logger.debug(msg2)
        # else:
        #     t_logger.debug(msg2)
        #     t_logger.debug(msg1)
        #
        # log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        #
        # if exp_error:
        #     with pytest.raises(UnmatchedExpectedMessages):
        #         log_ver.verify_log_results(log_results)
        # else:
        #     log_ver.verify_log_results(log_results)
        #
        # expected_result = "\n"
        # expected_result += f"{msgs_are_same_arg=}\n\n"
        # expected_result += f"{add_pattern1_first_arg=}\n\n"
        # expected_result += f"{issue_msg1_first_arg=}\n\n"
        # expected_result += f"{pattern1_fullmatch_tf_arg=}\n\n"
        # expected_result += f"{pattern2_fullmatch_tf_arg=}\n"
        #
        # expected_result += "\n"
        # expected_result += "**********************************\n"
        # expected_result += "* number expected log records: 2 *\n"
        #
        # if exp_error:
        #     expected_result += "* number expected unmatched  : 1 *\n"
        # else:
        #     expected_result += "* number expected unmatched  : 0 *\n"
        #
        # expected_result += "* number actual log records  : 2 *\n"
        #
        # if exp_error:
        #     expected_result += "* number actual unmatched    : 1 *\n"
        #     expected_result += "* number matched records     : 1 *\n"
        # else:
        #     expected_result += "* number actual unmatched    : 0 *\n"
        #     expected_result += "* number matched records     : 2 *\n"
        #
        # expected_result += "**********************************\n"
        # expected_result += "\n"
        # expected_result += "*********************************\n"
        # expected_result += "* unmatched expected records    *\n"
        # expected_result += "* (logger name, level, message) *\n"
        # expected_result += "*********************************\n"
        # if exp_error:
        #     expected_result += f"('fullmatch_0', 10, '{pattern1}')\n"
        #
        # expected_result += "\n"
        # expected_result += "*********************************\n"
        # expected_result += "* unmatched actual records      *\n"
        # expected_result += "* (logger name, level, message) *\n"
        # expected_result += "*********************************\n"
        # if exp_error:
        #     expected_result += f"('fullmatch_0', 10, '{msg2}')\n"
        #
        # expected_result += "\n"
        # expected_result += "*********************************\n"
        # expected_result += "* matched records               *\n"
        # expected_result += "* (logger name, level, message) *\n"
        # expected_result += "*********************************\n"
        # # if issue_msg1_first_arg:
        # #     expected_result += f"('fullmatch_0', 10, '{msg1}')\n"
        # #     expected_result += f"('fullmatch_0', 10, '{msg2}')\n"
        # # else:
        # #     expected_result += f"('fullmatch_0', 10, '{msg2}')\n"
        # #     expected_result += f"('fullmatch_0', 10, '{msg1}')\n"
        # if first_found == msg1:
        #     expected_result += f"('fullmatch_0', 10, '{msg1}')\n"
        #     if not exp_error:
        #         expected_result += f"('fullmatch_0', 10, '{msg2}')\n"
        # else:
        #     expected_result += f"('fullmatch_0', 10, '{msg2}')\n"
        #     expected_result += f"('fullmatch_0', 10, '{msg1}')\n"
        #
        # captured = capsys.readouterr().out
        #
        # assert captured == expected_result

    ####################################################################
    # test_log_verifier_time_match
    ####################################################################
    def test_log_verifier_time_match(
        self, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test log_verifier time match.

        Args:
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        t_logger = logging.getLogger("time_match")
        log_ver = LogVer(log_name="time_match")
        fmt_str = "%d %b %Y %H:%M:%S"

        match_str = get_datetime_match_string(fmt_str)
        time_str = datetime.datetime.now().strftime(fmt_str)

        exp_msg = f"the date and time is: {match_str}"
        act_msg = f"the date and time is: {time_str}"
        log_ver.add_msg(log_msg=exp_msg, log_name="time_match")
        t_logger.debug(act_msg)
        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 1 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 1 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        log_msg = f"the date and time is: {time_str}"
        expected_result += f"('time_match', 10, '{log_msg}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_add_call_seq
    ####################################################################
    def test_log_verifier_add_call_seq(
        self,
        simple_str_arg: str,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier add_call_seq method.

        Args:
            simple_str_arg: string to use in the message
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        t_logger = logging.getLogger("call_seq")
        log_ver = LogVer(log_name="call_seq")

        log_ver.add_call_seq(name="alpha", seq=simple_str_arg)
        log_ver.add_msg(log_msg=log_ver.get_call_seq("alpha"))
        t_logger.debug(f"{simple_str_arg}:{123}")
        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 1 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 1 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('call_seq', 10, '{simple_str_arg}:{123}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_add_call_seq2
    ####################################################################
    def test_log_verifier_add_call_seq2(
        self,
        simple_str_arg: str,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier add_call_seq method.

        Args:
            simple_str_arg: string to use in the message
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        t_logger = logging.getLogger("call_seq2")
        log_ver = LogVer(log_name="call_seq2")

        log_ver.add_call_seq(
            name="alpha",
            seq=(
                "test_log_verifier.py::TestLogVerBasic"
                ".test_log_verifier_add_call_seq2"
            ),
        )
        log_ver.add_msg(log_msg=log_ver.get_call_seq("alpha"))
        # t_logger.debug(f'{simple_str_arg}:{get_formatted_call_sequence()}')
        my_seq = get_formatted_call_sequence(depth=1)
        t_logger.debug(f"{my_seq}")
        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 1 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 1 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('call_seq2', 10, '{my_seq}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_add_call_seq3
    ####################################################################
    def test_log_verifier_add_call_seq3(
        self,
        simple_str_arg: str,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier add_call_seq method.

        Args:
            simple_str_arg: string to use in the message
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        t_logger = logging.getLogger("call_seq3")
        log_ver = LogVer(log_name="call_seq3")

        log_ver.add_call_seq(
            name="alpha",
            seq=(
                "test_log_verifier.py::TestLogVerBasic"
                ".test_log_verifier_add_call_seq3"
            ),
        )

        esc_thread_str = re.escape(f"{threading.current_thread()}")
        add_msg = (
            f"{esc_thread_str} "
            f"{simple_str_arg} "
            f'{log_ver.get_call_seq(name="alpha")}'
        )
        log_ver.add_msg(log_msg=add_msg)

        log_msg = (
            f"{threading.current_thread()} "
            f"{simple_str_arg} "
            f"{get_formatted_call_sequence(depth=1)}"
        )
        t_logger.debug(log_msg)

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 1 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 1 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('call_seq3', 10, '{log_msg}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_no_log
    ####################################################################
    def test_log_verifier_no_log(
        self,
        log_enabled_arg: bool,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier with logging disabled and enabled.

        Args:
            log_enabled_arg: fixture to indicate whether log is enabled
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        t_logger = logging.getLogger("no_log")
        log_ver = LogVer(log_name="no_log")
        if log_enabled_arg:
            t_logger.setLevel(logging.DEBUG)
        else:
            t_logger.setLevel(logging.INFO)

        log_msg = f"the log_enabled_arg is: {log_enabled_arg}"
        log_ver.add_msg(log_msg=log_msg)
        t_logger.debug(log_msg)
        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        if log_enabled_arg:
            log_ver.verify_log_results(log_results)
        else:
            with pytest.raises(UnmatchedExpectedMessages):
                log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 1 *\n"

        if log_enabled_arg:
            expected_result += "* number expected unmatched  : 0 *\n"
            expected_result += "* number actual log records  : 1 *\n"
        else:
            expected_result += "* number expected unmatched  : 1 *\n"
            expected_result += "* number actual log records  : 0 *\n"

        expected_result += "* number actual unmatched    : 0 *\n"

        if log_enabled_arg:
            expected_result += "* number matched records     : 1 *\n"
        else:
            expected_result += "* number matched records     : 0 *\n"

        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        if not log_enabled_arg:
            expected_result += "('no_log', " "10, 'the log_enabled_arg is: False')\n"

        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"

        if log_enabled_arg:
            expected_result += "('no_log', " "10, 'the log_enabled_arg is: True')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result


########################################################################
# TestLogVerBasic class
########################################################################
@pytest.mark.cover2
class TestLogVerCombos:
    """Test LogVer with various combinations."""

    ####################################################################
    # test_log_verifier_remaining_time1
    ####################################################################
    def test_log_verifier_combos(
        self,
        num_exp_msgs1: int,
        num_exp_msgs2: int,
        num_exp_msgs3: int,
        num_act_msgs1: int,
        num_act_msgs2: int,
        num_act_msgs3: int,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
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
        t_logger = logging.getLogger("combos")
        log_ver = LogVer(log_name="combos")

        total_num_exp_msgs = 0
        total_num_act_msgs = 0
        total_num_exp_unmatched = 0
        total_num_act_unmatched = 0
        total_num_matched = 0

        exp_unmatched_msgs = []
        act_unmatched_msgs = []
        matched_msgs = []

        msg_table = [
            (num_exp_msgs1, num_act_msgs1, "msg one"),
            (num_exp_msgs2, num_act_msgs2, "msg two"),
            (num_exp_msgs3, num_act_msgs3, "msg three"),
        ]

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
                t_logger.debug(the_msg)

            for _ in range(num_exp_unmatched):
                exp_unmatched_msgs.append(the_msg)

            for _ in range(num_act_unmatched):
                act_unmatched_msgs.append(the_msg)

            for _ in range(num_matched_msgs):
                matched_msgs.append(the_msg)

        max_of_totals = max(
            total_num_exp_msgs,
            total_num_act_msgs,
            total_num_exp_unmatched,
            total_num_act_unmatched,
            total_num_matched,
        )

        len_max_total = len(str(max_of_totals))
        asterisks = "*********************************" + "*" * len_max_total

        num_exp_space = len_max_total - len(str(total_num_exp_msgs))
        num_exp_unm_space = len_max_total - len(str(total_num_exp_unmatched))
        num_act_space = len_max_total - len(str(total_num_act_msgs))
        num_act_unm_space = len_max_total - len(str(total_num_act_unmatched))
        num_matched_space = len_max_total - len(str(total_num_matched))

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))

        if total_num_exp_unmatched:
            with pytest.raises(UnmatchedExpectedMessages):
                log_ver.verify_log_results(log_results)
        elif total_num_act_unmatched:
            with pytest.raises(UnmatchedActualMessages):
                log_ver.verify_log_results(log_results)
        else:
            log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += asterisks + "\n"
        expected_result += (
            "* number expected log records: "
            + " " * num_exp_space
            + f"{total_num_exp_msgs} *\n"
        )
        expected_result += (
            "* number expected unmatched  : "
            + " " * num_exp_unm_space
            + f"{total_num_exp_unmatched} *\n"
        )
        expected_result += (
            "* number actual log records  : "
            + " " * num_act_space
            + f"{total_num_act_msgs} *\n"
        )
        expected_result += (
            "* number actual unmatched    : "
            + " " * num_act_unm_space
            + f"{total_num_act_unmatched} *\n"
        )
        expected_result += (
            "* number matched records     : "
            + " " * num_matched_space
            + f"{total_num_matched} *\n"
        )
        expected_result += asterisks + "\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"

        for msg in exp_unmatched_msgs:
            expected_result += f"('combos', 10, '{msg}')\n"

        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"

        for msg in act_unmatched_msgs:
            expected_result += f"('combos', 10, '{msg}')\n"

        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"

        for msg in matched_msgs:
            expected_result += f"('combos', 10, '{msg}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result


########################################################################
# TestLogVerScratch class
########################################################################
class TestLogVerScratch:
    """Test LogVer with various combinations."""

    double_str_arg_list = [("a1", "a12"), ("b_2", "b_23"), ("xyz_567", "xyz_5678")]

    @pytest.mark.parametrize("double_str_arg", double_str_arg_list)
    def test_log_verifier_scratch(
        self,
        double_str_arg: str,
        # capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier time match.

        Args:
            double_str_arg: string to use in the message
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        ################################################################
        # step 0: use non-fullmatch in controlled way to cause success
        ################################################################
        log_name = "fullmatch_0"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        log_ver.add_msg(log_msg=double_str_arg[0])
        log_ver.add_msg(log_msg=double_str_arg[1])

        t_logger.debug(double_str_arg[0])
        t_logger.debug(double_str_arg[1])

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 2 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 2 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_0', 10, '{double_str_arg[0]}')\n"
        expected_result += f"('fullmatch_0', 10, '{double_str_arg[1]}')\n"

        # captured = capsys.readouterr().out
        #
        # assert captured == expected_result

        ################################################################
        # step 1: use non-fullmatch in controlled way to cause error
        ################################################################
        caplog.clear()

        log_name = "fullmatch_1"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        log_ver.add_msg(log_msg=double_str_arg[0])
        log_ver.add_msg(log_msg=double_str_arg[1])

        t_logger.debug(double_str_arg[1])
        t_logger.debug(double_str_arg[0])

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))

        with pytest.raises(UnmatchedExpectedMessages):
            log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 1 *\n"
        expected_result += "* number actual log records  : 2 *\n"
        expected_result += "* number actual unmatched    : 1 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_1', 10, '{double_str_arg[1]}')\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_1', 10, '{double_str_arg[0]}')\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_1', 10, '{double_str_arg[1]}')\n"

        # captured = capsys.readouterr().out
        #
        # assert captured == expected_result

        ################################################################
        # step 2: use fullmatch in controlled way - should succeed
        ################################################################
        caplog.clear()

        log_name = "fullmatch_2"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        log_ver.add_msg(log_msg=double_str_arg[0], fullmatch=True)
        log_ver.add_msg(log_msg=double_str_arg[1], fullmatch=True)

        t_logger.debug(double_str_arg[0])
        t_logger.debug(double_str_arg[1])

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))
        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 2 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 2 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_2', 10, '{double_str_arg[0]}')\n"
        expected_result += f"('fullmatch_2', 10, '{double_str_arg[1]}')\n"

        # captured = capsys.readouterr().out
        #
        # assert captured == expected_result

        ################################################################
        # step 3: use fullmatch in error case and expect success
        ################################################################
        caplog.clear()

        log_name = "fullmatch_3"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        log_ver.add_msg(log_msg=double_str_arg[0], fullmatch=True)
        log_ver.add_msg(log_msg=double_str_arg[1], fullmatch=True)

        t_logger.debug(double_str_arg[1])
        t_logger.debug(double_str_arg[0])

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))

        log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 0 *\n"
        expected_result += "* number actual log records  : 2 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 2 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_3', 10, '{double_str_arg[1]}')\n"
        expected_result += f"('fullmatch_3', 10, '{double_str_arg[0]}')\n"

        # captured = capsys.readouterr().out
        #
        # assert captured == expected_result

        ################################################################
        # step 4: use fullmatch and cause unmatched expected failure
        ################################################################
        caplog.clear()

        log_name = "fullmatch_4"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        log_ver.add_msg(log_msg=double_str_arg[0], fullmatch=True)
        log_ver.add_msg(log_msg=double_str_arg[1], fullmatch=True)

        t_logger.debug(double_str_arg[0])
        # t_logger.debug(double_str_arg[1])

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))

        with pytest.raises(UnmatchedExpectedMessages):
            log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += "**********************************\n"
        expected_result += "* number expected log records: 2 *\n"
        expected_result += "* number expected unmatched  : 1 *\n"
        expected_result += "* number actual log records  : 1 *\n"
        expected_result += "* number actual unmatched    : 0 *\n"
        expected_result += "* number matched records     : 1 *\n"
        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_4', 10, '{double_str_arg[1]}')\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        expected_result += f"('fullmatch_4', 10, '{double_str_arg[0]}')\n"

        # captured = capsys.readouterr().out
        #
        # assert captured == expected_result
