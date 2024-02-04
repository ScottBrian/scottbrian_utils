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
    # test_etrace_combo_signature
    ####################################################################
    # @pytest.mark.parametrize("num_po_arg", [0, 1, 2])
    def test_etrace_combo_signature(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """
        # exec("def f1(a): return a")
        # def f1(a): return 5
        # f2 = locals()["f1"]
        # exec("def f1(a): return 4")
        # def eval("f2(a)"): return a
        # f2 = locals()["f1"]
        # print("\n", locals())
        # f2 = f1
        # f2 = etrace(f2)

        # print(f2)

        # l1 = f"def f1(a): return a"
        # l2 = f"f1 = etrace(f1)"

        # code = f"{l1};{l2}"

        # code = f"z + x + y;print(z)"

        # exec("def f1(a): return a;f1 = etrace(f1)")

        # f2 = locals()["f1"]

        # f2 = etrace(f2)

        # code = f"def deco():\n    def f1(a): \n        return a\n    return f1"

        # exec(code)
        # print("\n", dir())
        # print("\n", locals())
        # deco = locals()["deco"]
        # f2 = deco()
        # exec("def f1(a): return a")
        # print("\n", dir())
        # print("\n", locals())
        # f1(42)
        # f2 = etrace(f1)
        #
        # f2(42)

        # print(z)

        # exec("global a;a = 42")

        # print(f"\n{f42(5)=}")

        # def make_code():
        #     def f41(a):
        #         return 15 + a
        #
        #     def f44(a):
        #         return 16 + a
        #
        #     # exec("def f41(a): return a\nf41 = etrace(f41)")
        #     exec(
        #         "global f42\ndef f47(a): return a\nf47 = etrace(f47)\nf42=f47",
        #         globals(),
        #         {"f41": f41, "f44": f44},
        #     )
        #     # f44 = etrace(f44)
        #     return f42
        #
        # f43 = make_code()
        # print(f"1 {f43(5)=}")
        # f42 = etrace(wrapped=f42)
        # f2(77)
        # def make_code():
        #     # exec("def f41(a): return a\nf41 = etrace(f41)")
        #     exec("def f47(a): return a\nf47 = etrace(f47)")
        #     f44 = locals()["f47"]
        #     return f44
        #
        # f43 = make_code()
        sig = "a"
        return_str = "return a"
        exec(f"def f42({sig}): {return_str}\nf43 = etrace(f42)")
        # exec("def f47(a): return a")
        f42 = locals()["f43"]
        # f43 = etrace(f43)
        print(f"1 {f42(5)=}")

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()

        file_name = "test_entry_trace.py"

        # f2(3)

        # ################################################################
        # # choose the target function or method
        # ################################################################
        # if target_type_arg == FunctionType.Function:
        #     target_rtn = f1
        #     target_line_num = inspect.getsourcelines(f1)[1]
        #     target_qual_name = ":f1"
        #
        # elif target_type_arg == FunctionType.Method:
        #     target_rtn = Target().target
        #     target_line_num = inspect.getsourcelines(Target.target)[1]
        #     target_qual_name = "::Target.target"
        #
        # elif target_type_arg == FunctionType.StaticMethod:
        #     target_rtn = Target().static_target
        #     target_line_num = inspect.getsourcelines(Target.static_target)[1]
        #     target_qual_name = "::Target.static_target"
        #
        # elif target_type_arg == FunctionType.ClassMethod:
        #     target_rtn = Target().class_target
        #     target_line_num = inspect.getsourcelines(Target.class_target)[1]
        #     target_qual_name = "::Target.class_target"
        #
        # elif target_type_arg == FunctionType.InitMethod:
        #     target_rtn = Target
        #     target_line_num = inspect.getsourcelines(Target.__init__)[1]
        #     target_qual_name = "::Target.__init__"
        #
        # ################################################################
        # # call the function or method
        # ################################################################
        # if caller_type_arg == FunctionType.Function:
        #     target_rtn()
        #     caller_qual_name = "TestEntryTraceCombos.test_etrace_combo_env"
        #
        # elif caller_type_arg == FunctionType.Method:
        #     Caller().caller()
        #     caller_qual_name = "Caller.caller"
        #
        # elif caller_type_arg == FunctionType.StaticMethod:
        #     Caller().static_caller()
        #     caller_qual_name = "Caller.static_caller"
        #
        # elif caller_type_arg == FunctionType.ClassMethod:
        #     Caller().class_caller()
        #     caller_qual_name = "Caller.class_caller"
        #
        # elif caller_type_arg == FunctionType.InitMethod:
        #     Caller()
        #     caller_qual_name = "Caller.__init__"
        #
        # exp_entry_log_msg = (
        #     rf"{file_name}{target_qual_name}:{target_line_num} entry: args=\(\), "
        #     "kwargs={}, "
        #     f"caller: {file_name}::{caller_qual_name}:[0-9]+"
        # )
        #
        # log_ver.add_msg(
        #     log_level=logging.DEBUG,
        #     log_msg=exp_entry_log_msg,
        #     log_name="scottbrian_utils.entry_trace",
        #     fullmatch=True,
        # )
        #
        # exp_exit_log_msg = (
        #     f"{file_name}{target_qual_name}:{target_line_num} exit: ret_value=None"
        # )
        #
        # log_ver.add_msg(
        #     log_level=logging.DEBUG,
        #     log_msg=exp_exit_log_msg,
        #     log_name="scottbrian_utils.entry_trace",
        #     fullmatch=True,
        # )
        # ################################################################
        # # check log results
        # ################################################################
        # match_results = log_ver.get_match_results(caplog=caplog)
        # log_ver.print_match_results(match_results, print_matched=True)
        # log_ver.verify_log_results(match_results)

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
