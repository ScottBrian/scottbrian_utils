"""test_entry_trace.py module."""

########################################################################
# Standard Library
########################################################################
from enum import Enum, auto
import logging
import datetime
import inspect
import re
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
                    eval(target_rtn)

            def caller(self):
                eval(target_rtn)

            @staticmethod
            def static_caller():
                eval(target_rtn)

            @classmethod
            def class_caller(cls):
                eval(target_rtn)

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

        if target_type_arg == FunctionType.Function:
            target_rtn = f1
            target_line_num = inspect.getsourcelines(f1)[1]
            target_qual_name = ":f1"

        elif target_type_arg == FunctionType.Method:
            target_rtn = "Target().target()"
            target_line_num = inspect.getsourcelines(Target.target)[1]
            target_qual_name = "::Target.target"

        elif target_type_arg == FunctionType.StaticMethod:
            target_rtn = "Target().static_target()"
            target_qual_name = "::Target.static_target"

        elif target_type_arg == FunctionType.ClassMethod:
            target_rtn = "Target().class_target()"
            target_qual_name = "::Target.class_target"

        elif target_type_arg == FunctionType.InitMethod:
            target_rtn = "Target()"
            target_qual_name = "::Target.__init__"

        if caller_type_arg == FunctionType.Function:
            if target_type_arg == FunctionType.Function:
                target_rtn()
            elif target_type_arg == FunctionType.Method:
                Target().target()
            elif target_type_arg == FunctionType.StaticMethod:
                Target().static_target()
            elif target_type_arg == FunctionType.ClassMethod:
                Target().class_target()
            elif target_type_arg == FunctionType.InitMethod:
                Target()
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
