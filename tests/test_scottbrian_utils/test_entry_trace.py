"""test_entry_trace.py module."""

########################################################################
# Standard Library
########################################################################
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum, auto
import functools as ft
import datetime
import inspect
import itertools as it
import logging
import more_itertools as mi
import re
import threading
from typing import Any, cast, Optional, Union

# from ast import *
# from types import *
import ast
import types

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.entry_trace import etrace
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

f999 = None


########################################################################
# EntryTrace test exceptions
########################################################################
class ErrorTstEntryTrace(Exception):
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
# TestEntryTraceExamples class
########################################################################
# @pytest.mark.cover2
class TestEntryTraceExamples:
    """Test examples of EntryTrace."""

    ####################################################################
    # test_etrace_example1
    ####################################################################
    def test_etrace_example1(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test etrace example1.

        Args:
            caplog: pytest fixture to capture log output

        """
        from scottbrian_utils.entry_trace import etrace

        @etrace
        def f1():
            pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        f1()

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py:f1:{f1_line_num} entry: args=\(\), "
            "kwargs={}, "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example1:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        exp_exit_log_msg = f"test_entry_trace.py:f1:{f1_line_num} exit: ret_value=None"

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_example2
    ####################################################################
    def test_etrace_example2(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test etrace example2.

        Args:
            caplog: pytest fixture to capture log output

        """
        from scottbrian_utils.entry_trace import etrace

        @etrace
        def f1(a1: int, kw1: str = "42"):
            return f"{a1=}, {kw1=}"

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        f1(42, kw1="forty two")

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py:f1:{f1_line_num} entry: args=\(42,\), "
            "kwargs={'kw1': 'forty two'}, "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example2:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        kw_value = "forty two"
        quote = "'"
        exp_exit_log_msg = (
            f'test_entry_trace.py:f1:{f1_line_num} exit: ret_value="a1=42, '
            f'kw1={quote}{kw_value}{quote}"'
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_example3
    ####################################################################
    def test_etrace_example3(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test etrace example3.

        Args:
            caplog: pytest fixture to capture log output

        """
        from scottbrian_utils.entry_trace import etrace

        do_trace: bool = True

        @etrace(enable_trace=do_trace)
        def f1(a1: int, kw1: str = "42"):
            return f"{a1=}, {kw1=}"

        do_trace: bool = False

        @etrace(enable_trace=do_trace)
        def f2(a1: int, kw1: str = "42"):
            return f"{a1=}, {kw1=}"

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        f1(42, kw1="forty two")
        f2(24, kw1="twenty four")

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py:f1:{f1_line_num} entry: args=\(42,\), "
            "kwargs={'kw1': 'forty two'}, "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example3:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        kw_value = "forty two"
        quote = "'"
        exp_exit_log_msg = (
            f'test_entry_trace.py:f1:{f1_line_num} exit: ret_value="a1=42, '
            f'kw1={quote}{kw_value}{quote}"'
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_example4
    ####################################################################
    def test_etrace_example4(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test etrace example4.

        Args:
            caplog: pytest fixture to capture log output

        """
        from scottbrian_utils.entry_trace import etrace

        @etrace(omit_args=True)
        def f1(a1: int, kw1: str = "42"):
            return f"{a1=}, {kw1=}"

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        f1(42, kw1="forty two")

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py:f1:{f1_line_num} entry: "
            "omit_args=True, kwargs={'kw1': 'forty two'}, "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example4:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        kw_value = "forty two"
        quote = "'"
        exp_exit_log_msg = (
            f'test_entry_trace.py:f1:{f1_line_num} exit: ret_value="a1=42, '
            f'kw1={quote}{kw_value}{quote}"'
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_example5
    ####################################################################
    def test_etrace_example5(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test etrace example5.

        Args:
            caplog: pytest fixture to capture log output

        """
        from scottbrian_utils.entry_trace import etrace

        @etrace(omit_kwargs="kw1")
        def f1(a1: int, kw1: str = "42", kw2: int = 24):
            return f"{a1=}, {kw1=}, {kw2=}"

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        f1(42, kw1="forty two", kw2=84)

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py:f1:{f1_line_num} entry: args=\(42,\), "
            "kwargs={'kw2': 84}, omit_kwargs={'kw1'}, "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example5:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        kw_value = "forty two"
        quote = "'"
        exp_exit_log_msg = (
            f'test_entry_trace.py:f1:{f1_line_num} exit: ret_value="a1=42, '
            f'kw1={quote}{kw_value}{quote}, kw2=84"'
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_example6
    ####################################################################
    def test_etrace_example6(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test etrace example6.

        Args:
            caplog: pytest fixture to capture log output

        """
        from scottbrian_utils.entry_trace import etrace

        @etrace
        def f1(a1: int, kw1: str = "42", kw2: int = 24):
            return f"{a1=}, {kw1=}, {kw2=}"

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()

        f1(42, kw1="forty two", kw2=84)

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py:f1:{f1_line_num} entry: args=\(42,\), "
            "kwargs={'kw1': 'forty two', 'kw2': 84}, "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example6:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        kw_value = "forty two"
        quote = "'"
        exp_exit_log_msg = (
            f'test_entry_trace.py:f1:{f1_line_num} exit: ret_value="a1=42, '
            f'kw1={quote}{kw_value}{quote}, kw2=84"'
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)


########################################################################
# TestEntryTraceBasic class
########################################################################
# @pytest.mark.cover2
class TestEntryTraceBasic:
    """Test basic functions of EntryTrace."""

    ####################################################################
    # test_etrace_on_function
    ####################################################################
    def test_etrace_on_function(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace
        def f1():
            pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        f1()

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py:f1:{f1_line_num} entry: args=\(\), "
            "kwargs={}, "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_function:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        exp_exit_log_msg = f"test_entry_trace.py:f1:{f1_line_num} exit: ret_value=None"

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_on_method
    ####################################################################
    def test_etrace_on_method(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace
            def f1(self):
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        Test1().f1()

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: args=\(\), "
            "kwargs={}, "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_method:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: ret_value=None"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_on_static_method
    ####################################################################
    def test_etrace_on_static_method(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a static method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace
            @staticmethod
            def f1():
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        Test1().f1()

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: args=\(\), "
            "kwargs={}, "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_static_method:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: ret_value=None"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_on_static_method
    ####################################################################
    def test_etrace_on_class_method(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace
            @classmethod
            def f1(cls):
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        Test1.f1()

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: args=\(\), "
            "kwargs={}, "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_class_method:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: ret_value=None"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_on_static_method
    ####################################################################
    def test_etrace_on_class_init_method(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace
            def __init__(self, v1: int):
                self.v1 = v1

            @classmethod
            def f1(cls):
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        Test1(42)

        f1_line_num = inspect.getsourcelines(Test1.__init__)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.__init__:{f1_line_num} entry: args=\(42,\), "
            "kwargs={}, "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_class_init_method:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.__init__:{f1_line_num} exit: ret_value=None"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)


########################################################################
# FunctionType
########################################################################
class FunctionType(Enum):
    """Resume scenario cases."""

    Function = auto()
    Method = auto()
    StaticMethod = auto()
    ClassMethod = auto()
    InitMethod = auto()


FunctionTypeList = [
    FunctionType.Function,
    FunctionType.Method,
    FunctionType.StaticMethod,
    FunctionType.ClassMethod,
    FunctionType.InitMethod,
]


########################################################################
# TestEntryTraceBasic class
########################################################################
@pytest.mark.cover2
class TestEntryTraceCombos:
    """Test EntryTrace with various combinations."""

    ####################################################################
    # test_etrace_combo_signature
    ####################################################################
    # @pytest.mark.parametrize("num_po_arg", [0, 1, 2, 3])
    # @pytest.mark.parametrize("num_pk_arg", [0, 1, 2, 3])
    # @pytest.mark.parametrize("num_ko_arg", [0, 1, 2, 3])
    @pytest.mark.parametrize("num_po_arg", [1])
    @pytest.mark.parametrize("num_pk_arg", [0])
    @pytest.mark.parametrize("num_ko_arg", [0])
    def test_etrace_combo_signature(
        self,
        num_po_arg: int,
        num_pk_arg: int,
        num_ko_arg: int,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            num_po_arg: number of position only parms
            num_pk_arg: number of position or keyword parms
            num_ko_arg: number of keyword only parms
            caplog: pytest fixture to capture log output

        """
        ################################################################
        # mainline
        ################################################################
        # definitions:
        # for combined pos_only and pos_or_kw groups, all defaults must
        # appear after non-defaults

        # no such rule for kw_only - any mix is ok and without regard
        # to how the pos_only and pos_or_kw groups are defined

        # invocations:
        # positionals must appear before kws

        # combinations of po_only with defaults
        # 0: none
        # 1: (a), (a=1)
        # 2: (a, b), (a, b=2), (a=1, b=2)
        # 3: (a, b, c), (a, b, c=3), (a, b=2, c=3), (a=1, b=2, c=3)

        # ways to call each group:
        # 0: f()
        # 1: (a): f(1)
        #    (a=1): f(), f(1)
        # 2: (a, b): f(1,2)
        #    (a, b=2): f(1,2), f(1)
        #    (a=1, b=2): f(1,2), f(1), f()
        # 3: (a, b, c): f(1, 2, 3)
        #    (a, b, c=3): f(1, 2, 3), f(1, 2)
        #    (a, b=2, c=3): f(1, 2, 3), f(1, 2), f(1)
        #    (a=1, b=2, c=3): f(1, 2, 3), f(1, 2), f(1), f()

        log_ver = LogVer()

        @dataclass
        class ArgSpecRetRes:
            arg_spec: str = ""
            log_result: str = ""
            ret_result: str = ""

            def __add__(self, other: "ArgSpecRetRes"):
                new_arg_spec = (self.arg_spec + other.arg_spec)[0:-2]
                new_log_result = self.log_result + other.log_result
                new_ret_result = self.ret_result + other.ret_result

                return ArgSpecRetRes(
                    new_arg_spec,
                    new_log_result,
                    new_ret_result,
                )

        @dataclass
        class OmitVariation:
            arg_specs_ret_reses: list[ArgSpecRetRes] = field(
                default_factory=lambda: [ArgSpecRetRes()]
            )
            omit_parms: list[str] = field(default_factory=list)

            def __add__(self, other: "OmitVariations"):
                combo_ret_reses = list(
                    it.product(self.arg_specs_ret_reses, other.arg_specs_ret_reses)
                )

                final_arg_specs: list[ArgSpecRetRes] = []
                for arg_spec in combo_ret_reses:
                    new_arg_spec = arg_spec[0] + arg_spec[1]
                    final_arg_specs.append(new_arg_spec)
                new_arg_specs_ret_reses = final_arg_specs

                new_omit_parms = self.omit_parms + other.omit_parms

                return OmitVariation(
                    arg_specs_ret_reses=new_arg_specs_ret_reses,
                    omit_parms=new_omit_parms,
                )

        class PlistType(Enum):
            """Request for SmartThread."""

            Po = auto()
            Pk = auto()
            Ko = auto()

        @dataclass
        class PlistSection:
            omit_variations: list[OmitVariation] = field(
                default_factory=lambda: [OmitVariation()]
            )
            plist: str = ""

            def __add__(self, other: "PlistSection"):
                combo_omit_variations = list(
                    it.product(self.omit_variations, other.omit_variations)
                )

                final_omit_variations: list[OmitVariation] = []
                for omit_variation in combo_omit_variations:
                    new_omit_variation = omit_variation[0] + omit_variation[1]
                    final_omit_variations.append(new_omit_variation)
                new_omit_variations = final_omit_variations
                new_plist = (self.plist + other.plist)[0:-2]

                return PlistSection(
                    omit_variations=new_omit_variations,
                    plist=new_plist,
                )

        class PlistSpec:
            raw_parms = {
                PlistType.Po: ("po_1", "po_2", "po_3"),
                PlistType.Pk: ("pk_4", "pk_5", "pk_6"),
                PlistType.Ko: ("ko_7", "ko_8", "ko_9"),
            }

            plist_prefix = {
                PlistType.Po: "",
                PlistType.Pk: "",
                PlistType.Ko: "*, ",
            }

            plist_suffix = {
                PlistType.Po: "/, ",
                PlistType.Pk: "",
                PlistType.Ko: "",
            }

            def __init__(
                self,
                num_po: int = 0,
                num_pk: int = 0,
                num_ko: int = 0,
            ):
                self.num_po = num_po
                self.num_pk = num_pk
                self.num_ko = num_ko

                self.raw_po_parms = list(self.raw_parms[PlistType.Po][0:num_po])
                self.raw_pk_parms = list(self.raw_parms[PlistType.Pk][0:num_pk])
                self.raw_ko_parms = list(self.raw_parms[PlistType.Ko][0:num_ko])

                self.ret_stmt = "".join(
                    list(
                        map(
                            self.set_ret_stmt,
                            self.raw_po_parms + self.raw_pk_parms + self.raw_ko_parms,
                        )
                    )
                )

                self.po_pk_raw_arg_specs = self.build_po_pk_arg_specs(num_pk=num_pk)

                self.ko_raw_arg_specs = [list(map(self.set_ko_args, self.raw_ko_parms))]

                # self.raw_arg_specs = self.build_arg_specs()

                # self.num_po_pk = num_po + num_pk
                # self.po_pk_def_array: list[int] = [0]
                # self.po_pk_sections: list[PlistSection] = []

                self.po_pk_sections = self.build_plist_section(
                    plist_parms=self.raw_po_parms + self.raw_pk_parms,
                    raw_arg_specs=self.po_pk_raw_arg_specs,
                    prefix_idx=0,
                    suffix_idx=num_po,
                )

                self.ko_sections = self.build_plist_section(
                    plist_parms=self.raw_ko_parms,
                    raw_arg_specs=self.ko_raw_arg_specs,
                    prefix_idx=self.num_ko,
                    suffix_idx=0,
                )

                self.final_plist_combos = map(
                    lambda x: x[0] + x[1],
                    it.product(self.po_pk_sections, self.ko_sections),
                )

            def build_po_pk_arg_specs(self, num_pk: int):
                po_raw_arg_spec = [list(map(self.set_po_args, self.raw_po_parms))]

                pk_raw_arg_specs = self.build_pk_arg_specs(num_pk=num_pk)

                pre_raw_arg_specs = list(it.product(po_raw_arg_spec, pk_raw_arg_specs))

                specs = [spec_item[0] + spec_item[1] for spec_item in pre_raw_arg_specs]

                return specs

            # def build_arg_specs(self):
            #     po_raw_arg_spec = [list(map(self.set_po_args, self.raw_po_parms))]
            #
            #     pk_raw_arg_specs = self.build_pk_arg_specs(num_pk=self.num_pk)
            #
            #     ko_raw_arg_spec = [list(map(self.set_ko_args, self.raw_ko_parms))]
            #
            #     pre_raw_arg_specs = list(
            #         it.product(po_raw_arg_spec, pk_raw_arg_specs, ko_raw_arg_spec)
            #     )
            #
            #     specs = [
            #         spec_item[0] + spec_item[1] + spec_item[2]
            #         for spec_item in pre_raw_arg_specs
            #     ]
            #
            #     return specs

            def build_pk_arg_specs(self, num_pk: int):
                arg_spec = [[]]
                if num_pk:
                    p_or_k_array = [0] * num_pk + [1] * num_pk

                    arg_spec = map(
                        self.do_pk_args, mi.sliding_window(p_or_k_array, num_pk)
                    )
                return arg_spec

            def build_plist_section(
                self, plist_parms, raw_arg_specs, prefix_idx, suffix_idx
            ) -> Iterable[PlistSection]:
                if plist_parms:
                    def_array = [1] * len(plist_parms) + [2] * len(plist_parms)
                else:
                    return [PlistSection()]  # base default section

                do_star2 = ft.partial(
                    self.do_star,
                    plist_parms=plist_parms,
                    raw_arg_specs=raw_arg_specs,
                    prefix_idx=prefix_idx,
                    suffix_idx=suffix_idx,
                )
                return map(do_star2, mi.sliding_window(def_array, len(plist_parms)))

            def do_pk_args(self, p_or_k_array):
                return list(
                    it.starmap(self.set_pk_args, zip(self.raw_pk_parms, p_or_k_array))
                )

            def do_star(
                self,
                def_list: list[int],
                *,
                plist_parms: list[str],
                raw_arg_specs: list[list[str]],
                prefix_idx: int,
                suffix_idx: int,
            ) -> PlistSection:
                plist_parts = list(
                    it.starmap(self.set_defaults, zip(plist_parms, def_list))
                )

                if prefix_idx:
                    plist = "".join(["*, "] + plist_parts)
                elif suffix_idx:
                    plist = "".join(
                        plist_parts[0:suffix_idx] + ["/, "] + plist_parts[suffix_idx:]
                    )
                else:
                    plist = "".join(plist_parts)

                omit_parms_powers_set = mi.powerset(plist_parms)
                # print(f"{list(omit_parms_powers_set)=}")

                omit_variations: list[OmitVariation] = []
                for omit_parm_parts in omit_parms_powers_set:
                    print(f"{omit_parm_parts=}")
                    if omit_parm_parts:
                        omit_parms = list(omit_parm_parts)
                    else:
                        omit_parms = []

                    print(f"55 {omit_parms=}")
                    # comma = ""
                    # for omit_part in omit_parm_parts:
                    #     omit_parms = f"{omit_parms}{comma}{omit_part}"
                    #     comma = ", "
                    #
                    # if omit_parms:
                    #     omit_parms = f"[{omit_parms}]"
                    # omit_parms = "".join(omit_parm_parts)

                    num_defs = sum(def_list) - len(def_list)
                    arg_spec_array = [1] * len(def_list) + [0] * num_defs

                    do_star_arg_spec2 = ft.partial(
                        self.do_star_arg_spec,
                        plist_parms=plist_parms,
                        omit_parm_parts=omit_parm_parts,
                        raw_arg_specs=raw_arg_specs,
                    )

                    arg_specs_ret_reses = list(
                        map(
                            do_star_arg_spec2,
                            mi.sliding_window(arg_spec_array, len(def_list)),
                        )
                    )

                    final_arg_specs = []
                    for item in arg_specs_ret_reses:
                        final_arg_specs += item

                    omit_variations.append(
                        OmitVariation(
                            arg_specs_ret_reses=final_arg_specs, omit_parms=omit_parms
                        )
                    )

                return PlistSection(omit_variations=omit_variations, plist=plist)

            def do_star_arg_spec(
                self,
                arg_spec_array: list[int],
                *,
                plist_parms: list[str],
                omit_parm_parts: tuple[str],
                raw_arg_specs: list[list[str]],
            ) -> Iterable[ArgSpecRetRes]:
                ret_res_parts = list(
                    it.starmap(self.set_ret_result, zip(plist_parms, arg_spec_array))
                )
                ret_res = "".join(ret_res_parts)

                for idx in range(len(plist_parms)):
                    if plist_parms[idx] in omit_parm_parts:
                        ret_res_parts[idx] = f"{plist_parms[idx]}='...', "

                log_result = "".join(ret_res_parts)

                def get_perms(raw_arg_spec: list[str]):
                    arg_spec_parts = list(
                        it.starmap(self.set_arg_spec, zip(raw_arg_spec, arg_spec_array))
                    )

                    left_args2, after_args = mi.before_and_after(
                        lambda x: "=" not in x, arg_spec_parts
                    )
                    mid_args, right_args2 = mi.before_and_after(
                        lambda x: "=" in x, after_args
                    )

                    if len(mid_args := list(mid_args)) > 1:
                        return list(
                            map(
                                lambda x: "".join(
                                    list(left_args2) + list(x) + list(right_args2)
                                ),
                                it.permutations(mid_args),
                            )
                        )
                    else:
                        return ["".join(arg_spec_parts)]

                return map(
                    lambda x: ArgSpecRetRes(
                        arg_spec=x,
                        log_result=log_result,
                        ret_result=ret_res,
                    ),
                    set(mi.collapse(map(get_perms, raw_arg_specs))),
                )

            @staticmethod
            def set_arg_spec(parm, selector):
                return ("", parm)[selector]

            @staticmethod
            def set_defaults(parm, selector):
                return parm + ("", ", ", f"={parm[-1]}, ")[selector]

            @staticmethod
            def set_po_args(parm):
                return f"{parm[-1]}0, "

            @staticmethod
            def set_pk_args(parm, selector):
                return (f"{parm[-1]}0, ", f"{parm}={parm[-1]}0, ")[selector]

            @staticmethod
            def set_ko_args(parm):
                return f"{parm}={parm[-1]}0, "

            @staticmethod
            def set_ret_result(parm, selector):
                return (f"{parm}={parm[-1]}, ", f"{parm}={parm[-1]}0, ")[selector]

            @staticmethod
            def set_ret_stmt(parm):
                p_str = f"{parm}="
                return "{" + p_str + "}, "

        plist_spec = PlistSpec(num_po=num_po_arg, num_pk=num_pk_arg, num_ko=num_ko_arg)

        for idx1, final_plist_combo in enumerate(plist_spec.final_plist_combos):
            for omit_variation in final_plist_combo.omit_variations:
                if omit_variation.omit_parms:
                    omit_parms_str = f",omit_parms={omit_variation.omit_parms}"
                else:
                    omit_parms_str = ""

                code = (
                    f"global f999"
                    f"\ndef f1({final_plist_combo.plist}): "
                    f"return f'{plist_spec.ret_stmt}'"
                    f"\nf1=etrace(f1{omit_parms_str})"
                    f"\nf999=f1"
                )

                plist_spec_log_msg = f"##################### {final_plist_combo.plist=}"
                # logger.debug(plist_spec_log_msg)
                log_ver.add_msg(
                    log_level=logging.DEBUG,
                    log_msg=re.escape(plist_spec_log_msg),
                    log_name="test_scottbrian_utils.test_entry_trace",
                    fullmatch=True,
                )
                exec(code)

                for idx2, arg_spec_ret_res in enumerate(
                    omit_variation.arg_specs_ret_reses
                ):
                    arg_spec_log_msg = (
                        f"##################### " f"{arg_spec_ret_res.arg_spec=}"
                    )
                    logger.debug(arg_spec_log_msg)
                    log_ver.add_msg(
                        log_level=logging.DEBUG,
                        log_msg=arg_spec_log_msg,
                        log_name="test_scottbrian_utils.test_entry_trace",
                        fullmatch=True,
                    )
                    exec(f"f999({arg_spec_ret_res.arg_spec})")

                    exp_entry_log_msg = (
                        rf"<string>:f1:\? entry: {arg_spec_ret_res.log_result}"
                        "caller: <string>:1"
                    )

                    log_ver.add_msg(
                        log_level=logging.DEBUG,
                        log_msg=exp_entry_log_msg,
                        log_name="scottbrian_utils.entry_trace",
                        fullmatch=True,
                    )

                    exp_exit_log_msg = (
                        rf"<string>:f1:\? exit: return_value='"
                        rf"{arg_spec_ret_res.ret_result}'"
                    )

                    log_ver.add_msg(
                        log_level=logging.DEBUG,
                        log_msg=exp_exit_log_msg,
                        log_name="scottbrian_utils.entry_trace",
                        fullmatch=True,
                    )

                print(f"\n{idx2=}")
        print(f"{idx1=}")
        print(f"{(idx1*idx2)=}")
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_combo_env
    ####################################################################
    @pytest.mark.parametrize("caller_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("target_type_arg", FunctionTypeList)
    def test_etrace_combo_env(
        self,
        caller_type_arg: FunctionType,
        target_type_arg: FunctionType,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caller_type_arg: type of function that makes the call
            caplog: pytest fixture to capture log output

        """
        if target_type_arg == FunctionType.InitMethod:
            trace_enabled = True
        else:
            trace_enabled = False

        @etrace
        def f1():
            pass

        class Caller:
            def __init__(self):
                if caller_type_arg == FunctionType.InitMethod:
                    target_rtn()

            def caller(self):
                target_rtn()

            @staticmethod
            def static_caller():
                target_rtn()

            @classmethod
            def class_caller(cls):
                target_rtn()

        class Target:
            @etrace(enable_trace=trace_enabled)
            def __init__(self):
                pass

            @etrace
            def target(self):
                pass

            @etrace
            @staticmethod
            def static_target():
                pass

            @etrace
            @classmethod
            def class_target(cls):
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()

        file_name = "test_entry_trace.py"

        ################################################################
        # choose the target function or method
        ################################################################
        if target_type_arg == FunctionType.Function:
            target_rtn = f1
            target_line_num = inspect.getsourcelines(f1)[1]
            target_qual_name = ":f1"

        elif target_type_arg == FunctionType.Method:
            target_rtn = Target().target
            target_line_num = inspect.getsourcelines(Target.target)[1]
            target_qual_name = "::Target.target"

        elif target_type_arg == FunctionType.StaticMethod:
            target_rtn = Target().static_target
            target_line_num = inspect.getsourcelines(Target.static_target)[1]
            target_qual_name = "::Target.static_target"

        elif target_type_arg == FunctionType.ClassMethod:
            target_rtn = Target().class_target
            target_line_num = inspect.getsourcelines(Target.class_target)[1]
            target_qual_name = "::Target.class_target"

        elif target_type_arg == FunctionType.InitMethod:
            target_rtn = Target
            target_line_num = inspect.getsourcelines(Target.__init__)[1]
            target_qual_name = "::Target.__init__"

        ################################################################
        # call the function or method
        ################################################################
        if caller_type_arg == FunctionType.Function:
            target_rtn()
            caller_qual_name = "TestEntryTraceCombos.test_etrace_combo_env"

        elif caller_type_arg == FunctionType.Method:
            Caller().caller()
            caller_qual_name = "Caller.caller"

        elif caller_type_arg == FunctionType.StaticMethod:
            Caller().static_caller()
            caller_qual_name = "Caller.static_caller"

        elif caller_type_arg == FunctionType.ClassMethod:
            Caller().class_caller()
            caller_qual_name = "Caller.class_caller"

        elif caller_type_arg == FunctionType.InitMethod:
            Caller()
            caller_qual_name = "Caller.__init__"

        exp_entry_log_msg = (
            rf"{file_name}{target_qual_name}:{target_line_num} entry: args=\(\), "
            "kwargs={}, "
            f"caller: {file_name}::{caller_qual_name}:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        exp_exit_log_msg = (
            f"{file_name}{target_qual_name}:{target_line_num} exit: ret_value=None"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_combo_parms
    ####################################################################
    @pytest.mark.parametrize("caller_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("target_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("num_args_arg", (0, 1, 2, 3, 4))
    @pytest.mark.parametrize("num_kwargs_arg", (0, 1, 2, 3, 4))
    def test_etrace_combo_parms(
        self,
        caller_type_arg: FunctionType,
        target_type_arg: FunctionType,
        num_args_arg: int,
        num_kwargs_arg: int,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caller_type_arg: type of function that makes the call
            caplog: pytest fixture to capture log output

        """
        if target_type_arg == FunctionType.InitMethod:
            trace_enabled = True
        else:
            trace_enabled = False

        @etrace
        def f1(*args, **kwargs):
            pass

        class Caller:
            def __init__(self):
                if caller_type_arg == FunctionType.InitMethod:
                    target_rtn(*target_args, **target_kwargs)

            def caller(self):
                target_rtn(*target_args, **target_kwargs)

            @staticmethod
            def static_caller():
                target_rtn(*target_args, **target_kwargs)

            @classmethod
            def class_caller(cls):
                target_rtn(*target_args, **target_kwargs)

        class Target:
            @etrace(enable_trace=trace_enabled)
            def __init__(self, *args, **kwargs):
                pass

            @etrace
            def target(self, *args, **kwargs):
                pass

            @etrace
            @staticmethod
            def static_target(*args, **kwargs):
                pass

            @etrace
            @classmethod
            def class_target(cls, *args, **kwargs):
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()

        file_name = "test_entry_trace.py"

        ################################################################
        # choose the target function or method
        ################################################################
        if target_type_arg == FunctionType.Function:
            target_rtn = f1
            target_line_num = inspect.getsourcelines(f1)[1]
            target_qual_name = ":f1"

        elif target_type_arg == FunctionType.Method:
            target_rtn = Target().target
            target_line_num = inspect.getsourcelines(Target.target)[1]
            target_qual_name = "::Target.target"

        elif target_type_arg == FunctionType.StaticMethod:
            target_rtn = Target().static_target
            target_line_num = inspect.getsourcelines(Target.static_target)[1]
            target_qual_name = "::Target.static_target"

        elif target_type_arg == FunctionType.ClassMethod:
            target_rtn = Target().class_target
            target_line_num = inspect.getsourcelines(Target.class_target)[1]
            target_qual_name = "::Target.class_target"

        elif target_type_arg == FunctionType.InitMethod:
            target_rtn = Target
            target_line_num = inspect.getsourcelines(Target.__init__)[1]
            target_qual_name = "::Target.__init__"

        ################################################################
        # setup the args
        ################################################################
        target_args = (1, 2.2, "three", [4, 4.4, "four", (4,)])
        target_args = target_args[0:num_args_arg]
        print(f"1 {target_args=}")

        ################################################################
        # setup the kwargs
        ################################################################
        target_kwargs = (
            ("v1", 1),
            ("v2", 2.2),
            ("v3", "three"),
            ("v4", [4, 4.4, "four", (4,)]),
        )
        target_kwargs = dict(target_kwargs[0:num_kwargs_arg])

        ################################################################
        # call the function or method
        ################################################################
        if caller_type_arg == FunctionType.Function:
            target_rtn(*target_args, **target_kwargs)
            caller_qual_name = "TestEntryTraceCombos.test_etrace_combo_parms"

        elif caller_type_arg == FunctionType.Method:
            Caller().caller()
            caller_qual_name = "Caller.caller"

        elif caller_type_arg == FunctionType.StaticMethod:
            Caller().static_caller()
            caller_qual_name = "Caller.static_caller"

        elif caller_type_arg == FunctionType.ClassMethod:
            Caller().class_caller()
            caller_qual_name = "Caller.class_caller"

        elif caller_type_arg == FunctionType.InitMethod:
            Caller()
            caller_qual_name = "Caller.__init__"

        exp_entry_log_msg = (
            rf"{file_name}{target_qual_name}:{target_line_num} entry: "
            rf"args={re.escape(str(target_args))}, "
            f"kwargs={re.escape(str(target_kwargs))}, "
            f"caller: {file_name}::{caller_qual_name}:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        exp_exit_log_msg = (
            f"{file_name}{target_qual_name}:{target_line_num} exit: ret_value=None"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_combo_omits
    ####################################################################
    @pytest.mark.parametrize("caller_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("target_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("omit_args_arg", (True, False))
    @pytest.mark.parametrize("num_kwargs_arg", (0, 1, 2, 3))
    @pytest.mark.parametrize("omit_kwargs_arg", (0, 1, 2, 3, 4, 5, 6, 7))
    @pytest.mark.parametrize("omit_ret_val_arg", (True, False))
    def test_etrace_combo_omits(
        self,
        caller_type_arg: FunctionType,
        target_type_arg: FunctionType,
        omit_args_arg: bool,
        num_kwargs_arg: int,
        omit_kwargs_arg: int,
        omit_ret_val_arg: bool,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caller_type_arg: type of function that makes the call
            target_type_arg: type of function to be called
            omit_args_arg: if true bool, don't trace args
            num_kwargs_arg: number of keywords args to build
            omit_kwargs_arg: int for binary mask
            omit_ret_val_arg: if True, omit ret value fro exit trace
            caplog: pytest fixture to capture log output

        """
        if target_type_arg == FunctionType.InitMethod:
            trace_enabled = True
        else:
            trace_enabled = False

        kwargs_to_omit: list[str] = []
        if omit_kwargs_arg in [1, 3, 5, 7]:
            kwargs_to_omit.append("v3")
        if omit_kwargs_arg in [4, 5, 6, 7]:
            kwargs_to_omit.append("v1")
        if omit_kwargs_arg in [2, 3, 6, 7]:
            kwargs_to_omit.append("v2")

        if num_kwargs_arg in [2, 3] and target_type_arg != FunctionType.InitMethod:
            ret_v2 = True
        else:
            ret_v2 = False

        @etrace(
            omit_args=omit_args_arg,
            omit_kwargs=kwargs_to_omit,
            omit_return_value=omit_ret_val_arg,
        )
        def f1(*args, **kwargs):
            if ret_v2:
                return kwargs["v2"]

        class Caller:
            def __init__(self):
                if caller_type_arg == FunctionType.InitMethod:
                    target_rtn(*target_args, **target_kwargs)

            def caller(self):
                target_rtn(*target_args, **target_kwargs)

            @staticmethod
            def static_caller():
                target_rtn(*target_args, **target_kwargs)

            @classmethod
            def class_caller(cls):
                target_rtn(*target_args, **target_kwargs)

        class Target:
            @etrace(
                enable_trace=trace_enabled,
                omit_args=omit_args_arg,
                omit_kwargs=kwargs_to_omit,
                omit_return_value=omit_ret_val_arg,
            )
            def __init__(self, *args, **kwargs):
                pass

            @etrace(
                omit_args=omit_args_arg,
                omit_kwargs=kwargs_to_omit,
                omit_return_value=omit_ret_val_arg,
            )
            def target(self, *args, **kwargs):
                if ret_v2:
                    return kwargs["v2"]

            @etrace(
                omit_args=omit_args_arg,
                omit_kwargs=kwargs_to_omit,
                omit_return_value=omit_ret_val_arg,
            )
            @staticmethod
            def static_target(*args, **kwargs):
                if ret_v2:
                    return kwargs["v2"]

            @etrace(
                omit_args=omit_args_arg,
                omit_kwargs=kwargs_to_omit,
                omit_return_value=omit_ret_val_arg,
            )
            @classmethod
            def class_target(cls, *args, **kwargs):
                if ret_v2:
                    return kwargs["v2"]

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()

        file_name = "test_entry_trace.py"

        ################################################################
        # choose the target function or method
        ################################################################
        if target_type_arg == FunctionType.Function:
            target_rtn = f1
            target_line_num = inspect.getsourcelines(f1)[1]
            target_qual_name = ":f1"

        elif target_type_arg == FunctionType.Method:
            target_rtn = Target().target
            target_line_num = inspect.getsourcelines(Target.target)[1]
            target_qual_name = "::Target.target"

        elif target_type_arg == FunctionType.StaticMethod:
            target_rtn = Target().static_target
            target_line_num = inspect.getsourcelines(Target.static_target)[1]
            target_qual_name = "::Target.static_target"

        elif target_type_arg == FunctionType.ClassMethod:
            target_rtn = Target().class_target
            target_line_num = inspect.getsourcelines(Target.class_target)[1]
            target_qual_name = "::Target.class_target"

        elif target_type_arg == FunctionType.InitMethod:
            target_rtn = Target
            target_line_num = inspect.getsourcelines(Target.__init__)[1]
            target_qual_name = "::Target.__init__"

        ################################################################
        # setup the args
        ################################################################
        target_args = (1, 2.2, "three", [4, 4.4, "four", (4,)])

        if omit_args_arg:
            log_target_args = "omit_args=True"
        else:
            log_target_args = f"args={re.escape(str(target_args))}"
        ################################################################
        # setup the kwargs
        ################################################################
        target_kwargs = (
            ("v1", 1),
            ("v2", 2.2),
            ("v3", "three"),
        )
        target_kwargs = dict(target_kwargs[0:num_kwargs_arg])

        log_target_kwargs = {}
        if num_kwargs_arg in [1, 2, 3] and omit_kwargs_arg in [0, 1, 2, 3]:
            log_target_kwargs["v1"] = target_kwargs["v1"]
        if num_kwargs_arg in [2, 3] and omit_kwargs_arg in [0, 1, 4, 5]:
            log_target_kwargs["v2"] = target_kwargs["v2"]
        if num_kwargs_arg == 3 and omit_kwargs_arg in [0, 2, 4, 6]:
            log_target_kwargs["v3"] = target_kwargs["v3"]

        if kwargs_to_omit:
            log_omit_kwargs = f" omit_kwargs={set(kwargs_to_omit)},"
        else:
            log_omit_kwargs = ""

        ################################################################
        # call the function or method
        ################################################################
        if caller_type_arg == FunctionType.Function:
            target_rtn(*target_args, **target_kwargs)
            caller_qual_name = "TestEntryTraceCombos.test_etrace_combo_omits"

        elif caller_type_arg == FunctionType.Method:
            Caller().caller()
            caller_qual_name = "Caller.caller"

        elif caller_type_arg == FunctionType.StaticMethod:
            Caller().static_caller()
            caller_qual_name = "Caller.static_caller"

        elif caller_type_arg == FunctionType.ClassMethod:
            Caller().class_caller()
            caller_qual_name = "Caller.class_caller"

        elif caller_type_arg == FunctionType.InitMethod:
            Caller()
            caller_qual_name = "Caller.__init__"

        exp_entry_log_msg = (
            rf"{file_name}{target_qual_name}:{target_line_num} entry: "
            rf"{log_target_args}, "
            f"kwargs={re.escape(str(log_target_kwargs))},{log_omit_kwargs} "
            f"caller: {file_name}::{caller_qual_name}:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        if omit_ret_val_arg:
            ret_value = "return value omitted"
        elif ret_v2:
            ret_value = "return_value=2.2"
        else:
            ret_value = "return_value=None"

        exp_exit_log_msg = (
            f"{file_name}{target_qual_name}:{target_line_num} exit: {ret_value}"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)

    ####################################################################
    # test_etrace_combo_omits
    ####################################################################
    @pytest.mark.parametrize("caller_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("target_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("omit_args_arg", (True, False))
    @pytest.mark.parametrize("num_kwargs_arg", (0, 1, 2, 3))
    @pytest.mark.parametrize("omit_kwargs_arg", (0, 1, 2, 3, 4, 5, 6, 7))
    @pytest.mark.parametrize("omit_ret_val_arg", (True, False))
    def test_etrace_combo_omits_2(
        self,
        caller_type_arg: FunctionType,
        target_type_arg: FunctionType,
        omit_args_arg: bool,
        num_kwargs_arg: int,
        omit_kwargs_arg: int,
        omit_ret_val_arg: bool,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caller_type_arg: type of function that makes the call
            target_type_arg: type of function to be called
            omit_args_arg: if true bool, don't trace args
            num_kwargs_arg: number of keywords args to build
            omit_kwargs_arg: int for binary mask
            omit_ret_val_arg: if True, omit ret value fro exit trace
            caplog: pytest fixture to capture log output

        """
        if target_type_arg == FunctionType.InitMethod:
            trace_enabled = True
        else:
            trace_enabled = False

        kwargs_to_omit: list[str] = []
        if omit_kwargs_arg in [1, 3, 5, 7]:
            kwargs_to_omit.append("kw3")
        if omit_kwargs_arg in [4, 5, 6, 7]:
            kwargs_to_omit.append("kw1")
        if omit_kwargs_arg in [2, 3, 6, 7]:
            kwargs_to_omit.append("kw2")

        @etrace(
            omit_args=omit_args_arg,
            omit_kwargs=kwargs_to_omit,
            omit_return_value=omit_ret_val_arg,
        )
        def f1(
            a1: int,
            a2: float,
            /,
            a3: str,
            *,
            kw1: int,
            kw2: float = 2.2,
            kw3: str = "three",
        ) -> list[int, float, str, int, float, str]:
            return [a1, a2, a3, kw1, kw2, kw3]

        class Caller:
            def __init__(self):
                if caller_type_arg == FunctionType.InitMethod:
                    target_rtn(*target_args, **target_kwargs)

            def caller(self):
                target_rtn(*target_args, **target_kwargs)

            @staticmethod
            def static_caller():
                target_rtn(*target_args, **target_kwargs)

            @classmethod
            def class_caller(cls):
                target_rtn(*target_args, **target_kwargs)

        class Target:
            @etrace(
                enable_trace=trace_enabled,
                omit_args=omit_args_arg,
                omit_kwargs=kwargs_to_omit,
                omit_return_value=omit_ret_val_arg,
            )
            def __init__(
                self,
                a1: int,
                a2: float,
                a3: str,
                *,
                kw1: int = 1,
                kw2: float = 2.2,
                kw3: str = "three",
            ) -> None:
                self.a1 = a1
                self.a2 = a2
                self.a3 = a3
                self.kw1 = kw1
                self.kw2 = kw2
                self.kw3 = kw3

            @etrace(
                omit_args=omit_args_arg,
                omit_kwargs=kwargs_to_omit,
                omit_return_value=omit_ret_val_arg,
            )
            def target(
                self,
                a1: int,
                a2: float,
                a3: str,
                *,
                kw1: int = 1,
                kw2: float = 2.2,
                kw3: str = "three",
            ) -> list[int, float, str, int, float, str]:
                return [a1, a2, a3, kw1, kw2, kw3]

            @etrace(
                omit_args=omit_args_arg,
                omit_kwargs=kwargs_to_omit,
                omit_return_value=omit_ret_val_arg,
            )
            @staticmethod
            def static_target(
                a1: int,
                a2: float,
                a3: str,
                *,
                kw1: int = 1,
                kw2: float = 2.2,
                kw3: str = "three",
            ) -> list[int, float, str, int, float, str]:
                return [a1, a2, a3, kw1, kw2, kw3]

            @etrace(
                omit_args=omit_args_arg,
                omit_kwargs=kwargs_to_omit,
                omit_return_value=omit_ret_val_arg,
            )
            @classmethod
            def class_target(
                cls,
                a1: int,
                a2: float,
                a3: str,
                *,
                kw1: int = 1,
                kw2: float = 2.2,
                kw3: str = "three",
            ) -> list[int, float, str, int, float, str]:
                return [a1, a2, a3, kw1, kw2, kw3]

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()

        file_name = "test_entry_trace.py"

        ################################################################
        # choose the target function or method
        ################################################################
        if target_type_arg == FunctionType.Function:
            target_rtn = f1
            target_line_num = inspect.getsourcelines(f1)[1]
            target_qual_name = ":f1"

        elif target_type_arg == FunctionType.Method:
            target_rtn = Target().target
            target_line_num = inspect.getsourcelines(Target.target)[1]
            target_qual_name = "::Target.target"

        elif target_type_arg == FunctionType.StaticMethod:
            target_rtn = Target().static_target
            target_line_num = inspect.getsourcelines(Target.static_target)[1]
            target_qual_name = "::Target.static_target"

        elif target_type_arg == FunctionType.ClassMethod:
            target_rtn = Target().class_target
            target_line_num = inspect.getsourcelines(Target.class_target)[1]
            target_qual_name = "::Target.class_target"

        elif target_type_arg == FunctionType.InitMethod:
            target_rtn = Target
            target_line_num = inspect.getsourcelines(Target.__init__)[1]
            target_qual_name = "::Target.__init__"

        ################################################################
        # setup the args
        ################################################################
        target_args = (1, 2.2, "three")

        if omit_args_arg:
            log_target_args = "omit_args=True"
        else:
            log_target_args = f"args={re.escape(str(target_args))}"
        ################################################################
        # setup the kwargs
        ################################################################
        target_kwargs = (
            ("kw1", 11),
            ("kw2", 22.22),
            ("kw3", "thrace"),
        )
        target_kwargs = dict(target_kwargs[0:num_kwargs_arg])

        log_target_kwargs = {"kw1": 1, "kw2": 2.2, "kw3": "three"}
        if num_kwargs_arg in [1, 2, 3] and omit_kwargs_arg in [0, 1, 2, 3]:
            log_target_kwargs["kw1"] = target_kwargs["kw1"]
        if num_kwargs_arg in [2, 3] and omit_kwargs_arg in [0, 1, 4, 5]:
            log_target_kwargs["kw2"] = target_kwargs["kw2"]
        if num_kwargs_arg == 3 and omit_kwargs_arg in [0, 2, 4, 6]:
            log_target_kwargs["kw3"] = target_kwargs["kw3"]

        if kwargs_to_omit:
            log_omit_kwargs = f" omit_kwargs={set(kwargs_to_omit)},"
        else:
            log_omit_kwargs = ""

        ################################################################
        # call the function or method
        ################################################################
        if caller_type_arg == FunctionType.Function:
            target_rtn(*target_args, **target_kwargs)
            caller_qual_name = "TestEntryTraceCombos.test_etrace_combo_omits_2"

        elif caller_type_arg == FunctionType.Method:
            Caller().caller()
            caller_qual_name = "Caller.caller"

        elif caller_type_arg == FunctionType.StaticMethod:
            Caller().static_caller()
            caller_qual_name = "Caller.static_caller"

        elif caller_type_arg == FunctionType.ClassMethod:
            Caller().class_caller()
            caller_qual_name = "Caller.class_caller"

        elif caller_type_arg == FunctionType.InitMethod:
            Caller()
            caller_qual_name = "Caller.__init__"

        exp_entry_log_msg = (
            rf"{file_name}{target_qual_name}:{target_line_num} entry: "
            rf"{log_target_args}, "
            f"kwargs={re.escape(str(log_target_kwargs))},{log_omit_kwargs} "
            f"caller: {file_name}::{caller_qual_name}:[0-9]+"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        if omit_ret_val_arg:
            ret_value = "return value omitted"
        elif target_type_arg == FunctionType.InitMethod:
            ret_value = "return_value=None"
        else:
            ret_value = (
                f"return_value=[1, 2.2, 'three', "
                f"{log_target_kwargs['kw1']}, "
                f"{log_target_kwargs['kw2']}, "
                f"{log_target_kwargs['kw3']}]"
            )

        exp_exit_log_msg = (
            f"{file_name}{target_qual_name}:{target_line_num} exit: {ret_value}"
        )

        log_ver.add_msg(
            log_level=logging.DEBUG,
            log_msg=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_log_results(match_results)
