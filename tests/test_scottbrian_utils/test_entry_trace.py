"""test_entry_trace.py module."""

########################################################################
# Standard Library
########################################################################
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum, auto
import functools as ft

import inspect
import itertools as it
import logging
import more_itertools as mi
import re

from typing import Any, Callable, Iterator, Optional, Union
from typing_extensions import Protocol

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.entry_trace import etrace
from scottbrian_utils.log_verifier import LogVer

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
# TestEntryTraceErrors class
########################################################################
class TestEntryTraceErrors:
    """TestEntryTraceErrors class."""

    ####################################################################
    # test_entry_trace_unknown_omit_parm
    ####################################################################
    def test_entry_trace_unknown_omit_parm(self) -> None:
        """Test bad pause min_interval_secs raises error."""

        from scottbrian_utils.entry_trace import etrace

        @etrace(omit_parms=["a2"])
        def f1(a1: int, kw1: str = "42") -> str:
            return f"{a1=}, {kw1=}"

        ################################################################
        # mainline
        ################################################################
        with pytest.raises(ValueError):
            f1(42, kw1="forty two")


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
        def f1() -> None:
            pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        f1()

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example1:[0-9]+"
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        exp_exit_log_msg = (
            f"test_entry_trace.py::f1:{f1_line_num} exit: " f"return_value=None"
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

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
        def f1(a1: int, kw1: str = "42") -> str:
            return f"{a1=}, {kw1=}"

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        f1(42, kw1="forty two")

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: a1=42, "
            "kw1='forty two', "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example2:[0-9]+"
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        kw_value = "forty two"
        quote = "'"
        exp_exit_log_msg = (
            f'test_entry_trace.py::f1:{f1_line_num} exit: return_value="a1=42, '
            f'kw1={quote}{kw_value}{quote}"'
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

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

        def do_trace_fn() -> bool:
            return do_trace

        @etrace(enable_trace=do_trace)
        def f1(a1: int, kw1: str = "42") -> str:
            return f"{a1=}, {kw1=}"

        do_trace = False

        @etrace(enable_trace=do_trace)
        def f2(a1: int, kw1: str = "42") -> str:
            return f"{a1=}, {kw1=}"

        @etrace(enable_trace=do_trace_fn)
        def f3(a1: int, kw1: str = "42") -> str:
            return f"{a1=}, {kw1=}"

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        f1(42, kw1="forty two")
        f2(24, kw1="twenty four")
        f3(84, kw1="eighty four")

        do_trace = True

        f3(12, kw1="twelve")

        f1_line_num = inspect.getsourcelines(f1)[1]
        f3_line_num = inspect.getsourcelines(f3)[1]

        ################################################################
        # f1 expected results
        ################################################################
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: a1=42, "
            "kw1='forty two', "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example3:[0-9]+"
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        kw_value = "forty two"
        quote = "'"
        exp_exit_log_msg = (
            f'test_entry_trace.py::f1:{f1_line_num} exit: return_value="a1=42, '
            f'kw1={quote}{kw_value}{quote}"'
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        ################################################################
        # f3 expected results
        ################################################################
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f3:{f3_line_num} entry: a1=12, "
            "kw1='twelve', "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example3:[0-9]+"
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        kw_value = "twelve"
        quote = "'"
        exp_exit_log_msg = (
            f'test_entry_trace.py::f3:{f3_line_num} exit: return_value="a1=12, '
            f'kw1={quote}{kw_value}{quote}"'
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_example4
    ####################################################################
    def test_etrace_example4(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test etrace example4.

        Args:
            caplog: pytest fixture to capture log output

        """
        from scottbrian_utils.entry_trace import etrace

        @etrace(omit_parms=["a1"])
        def f1(a1: int, kw1: str = "42") -> str:
            return f"{a1=}, {kw1=}"

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()
        f1(42, kw1="forty two")

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: a1='...', "
            "kw1='forty two', "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example4:[0-9]+"
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        kw_value = "forty two"
        quote = "'"
        exp_exit_log_msg = (
            f'test_entry_trace.py::f1:{f1_line_num} exit: return_value="a1=42, '
            f'kw1={quote}{kw_value}{quote}"'
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_example5
    ####################################################################
    def test_etrace_example5(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test etrace example5.

        Args:
            caplog: pytest fixture to capture log output

        """
        from scottbrian_utils.entry_trace import etrace

        @etrace(omit_parms="kw1")
        def f1(a1: int, kw1: str = "42", kw2: int = 24) -> str:
            return f"{a1=}, {kw1=}, {kw2=}"

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1(42, kw1="forty two", kw2=84)

        f1_line_num = inspect.getsourcelines(f1)[1]

        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: a1=42, "
            "kw1='...', kw2=84, "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example5:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)
        kw_value = "forty two"
        quote = "'"
        exp_exit_log_msg = (
            f'test_entry_trace.py::f1:{f1_line_num} exit: return_value="a1=42, '
            f'kw1={quote}{kw_value}{quote}, kw2=84"'
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_example6
    ####################################################################
    def test_etrace_example6(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test etrace example6.

        Args:
            caplog: pytest fixture to capture log output

        """
        from scottbrian_utils.entry_trace import etrace

        @etrace(omit_return_value=True)
        def f1(a1: int, kw1: str = "42", kw2: int = 24) -> str:
            return f"{a1=}, {kw1=}, {kw2=}"

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")

        f1(42, kw1="forty two", kw2=84)

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: a1=42, "
            "kw1='forty two', kw2=84, "
            "caller: test_entry_trace.py::TestEntryTraceExamples."
            "test_etrace_example6:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::f1:{f1_line_num} exit: return value omitted"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)


########################################################################
# TestEntryTraceBasic class
########################################################################
# @pytest.mark.cover2
class TestEntryTraceBasic:
    """Test basic functions of EntryTrace."""

    ####################################################################
    # test_etrace_on_function_no_parm
    ####################################################################
    def test_etrace_on_function_no_parm(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace
        def f1() -> None:
            pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1()

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_function_no_parm:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_no_parm2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_function_no_parm2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        @etrace(log_ver=log_ver)
        def f1() -> None:
            pass

        ################################################################
        # mainline
        ################################################################
        f1()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_no_parm
    ####################################################################
    def test_etrace_on_function_no_parm3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace(omit_caller=True)
        def f1() -> None:
            pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1()

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = rf"test_entry_trace.py::f1:{f1_line_num} entry:"

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_no_parm4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_function_no_parm4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        @etrace(omit_caller=True, log_ver=log_ver)
        def f1() -> None:
            pass

        ################################################################
        # mainline
        ################################################################
        f1()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_nested_functions
    ####################################################################
    @pytest.mark.parametrize("latest_arg", (1, 2, 3, 4, 5))
    @pytest.mark.parametrize("depth_arg", (1, 2, 3, 4, 5))
    @pytest.mark.parametrize("f3_depth_arg", (1, 2, 3, 4))
    @pytest.mark.parametrize("f2_trace_enable_arg", (True, False))
    @pytest.mark.parametrize("f3_trace_enable_arg", (True, False))
    def test_etrace_on_nested_functions(
        self,
        latest_arg: int,
        depth_arg: int,
        f3_depth_arg: int,
        f2_trace_enable_arg: bool,
        f3_trace_enable_arg: bool,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            latest_arg: latest arg for etrace
            depth_arg: depth arg for etrace
            f3_depth_arg: depth arg for etrace for f3
            f2_trace_enable_arg: specifies etrace enable for f2
            f3_trace_enable_arg: specifies etrace enable for f3
            caplog: pytest fixture to capture log output

        """
        f5_max_latest = 5
        if not f2_trace_enable_arg:
            f5_max_latest -= 1
        if not f3_trace_enable_arg:
            f5_max_latest -= 1
        f5_latest = min(f5_max_latest, latest_arg)

        @etrace
        def f1() -> None:
            f2()

        @etrace(enable_trace=f2_trace_enable_arg)
        def f2() -> None:
            f3()

        @etrace(enable_trace=f3_trace_enable_arg, depth=f3_depth_arg)
        def f3() -> None:
            f4()

        @etrace(latest=latest_arg)
        def f4() -> None:
            f5()

        @etrace(latest=f5_latest, depth=depth_arg)
        def f5() -> None:
            pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1()

        ################################################################
        # fn line numbers
        ################################################################
        f1_line_num = inspect.getsourcelines(f1)[1]
        f2_line_num = inspect.getsourcelines(f2)[1]
        f3_line_num = inspect.getsourcelines(f3)[1]
        f4_line_num = inspect.getsourcelines(f4)[1]
        f5_line_num = inspect.getsourcelines(f5)[1]

        ################################################################
        # fn entry/exit strings
        ################################################################
        f1_entry_exit = f"test_entry_trace.py::f1:{f1_line_num}"
        f2_entry_exit = f"test_entry_trace.py::f2:{f2_line_num}"
        f3_entry_exit = f"test_entry_trace.py::f3:{f3_line_num}"
        f4_entry_exit = f"test_entry_trace.py::f4:{f4_line_num}"
        f5_entry_exit = f"test_entry_trace.py::f5:{f5_line_num}"

        ################################################################
        # caller strings
        ################################################################
        ml_seq = (
            "test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_nested_functions:[0-9]+"
        )
        f1_seq = "test_entry_trace.py::f1:[0-9]+"
        f2_seq = "test_entry_trace.py::f2:[0-9]+"
        f3_seq = "test_entry_trace.py::f3:[0-9]+"
        f4_seq = "test_entry_trace.py::f4:[0-9]+"
        tw_seq = "entry_trace.py::trace_wrapper:[0-9]+"

        ################################################################
        # f1 expected trace results
        ################################################################
        f1_call_seq = f"{ml_seq}"
        log_ver.add_pattern(pattern=f"{f1_entry_exit} entry: caller: {f1_call_seq}")
        log_ver.add_pattern(pattern=f"{f1_entry_exit} exit: return_value=None")

        ################################################################
        # f2 expected trace results
        ################################################################
        f2_call_seq = f"{f1_seq}"
        if f2_trace_enable_arg:
            log_ver.add_pattern(pattern=f"{f2_entry_exit} entry: caller: {f2_call_seq}")
            log_ver.add_pattern(pattern=f"{f2_entry_exit} exit: return_value=None")

        ################################################################
        # f3 expected trace results
        ################################################################
        if f2_trace_enable_arg:
            pos_1 = f2_seq
            pos_2 = tw_seq
            pos_3 = f1_seq
            pos_4 = tw_seq
        else:
            pos_1 = f2_seq
            pos_2 = f1_seq
            pos_3 = tw_seq
            pos_4 = ml_seq

        if f3_depth_arg == 1:
            f3_call_seq = f"{pos_1}"
        elif f3_depth_arg == 2:
            f3_call_seq = f"{pos_2} -> {pos_1}"
        elif f3_depth_arg == 3:
            f3_call_seq = f"{pos_3} -> {pos_2} -> {pos_1}"
        else:
            f3_call_seq = f"{pos_4} -> {pos_3} -> {pos_2} -> {pos_1}"

        if f3_trace_enable_arg:
            log_ver.add_pattern(pattern=f"{f3_entry_exit} entry: caller: {f3_call_seq}")
            log_ver.add_pattern(pattern=f"{f3_entry_exit} exit: return_value=None")

        ################################################################
        # f4 expected trace results
        ################################################################
        pos_1 = f4_seq
        pos_2 = tw_seq
        pos_3 = f3_seq
        pos_4 = tw_seq
        pos_5 = f2_seq
        pos_6 = tw_seq
        pos_7 = f1_seq
        pos_8 = tw_seq
        pos_9 = ml_seq
        if not f3_trace_enable_arg:
            pos_4 = pos_5
            pos_5 = pos_6
            pos_6 = pos_7
            pos_7 = pos_8
            pos_8 = pos_9
        if not f2_trace_enable_arg:
            if not f3_trace_enable_arg:
                pos_5 = pos_6
            pos_6 = pos_7
            pos_7 = pos_8
            pos_8 = pos_9
        if latest_arg == 1:
            f4_call_seq = f"{pos_3}"
        elif latest_arg == 2:
            f4_call_seq = f"{pos_4}"
        elif latest_arg == 3:
            f4_call_seq = f"{pos_5}"
        elif latest_arg == 4:
            f4_call_seq = f"{pos_6}"
        else:
            f4_call_seq = f"{pos_7}"

        log_ver.add_pattern(pattern=f"{f4_entry_exit} entry: caller: {f4_call_seq}")
        log_ver.add_pattern(pattern=f"{f4_entry_exit} exit: return_value=None")

        ################################################################
        # f5 expected trace results
        ################################################################
        pos_1 = f4_seq
        pos_2 = tw_seq
        pos_3 = f3_seq
        pos_4 = tw_seq
        pos_5 = f2_seq
        pos_6 = tw_seq
        pos_7 = f1_seq
        pos_8 = tw_seq
        pos_9 = ml_seq
        if not f3_trace_enable_arg:
            pos_4 = pos_5
            pos_5 = pos_6
            pos_6 = pos_7
            pos_7 = pos_8
            pos_8 = pos_9
        if not f2_trace_enable_arg:
            if not f3_trace_enable_arg:
                pos_5 = pos_6
            pos_6 = pos_7
            pos_7 = pos_8
            pos_8 = pos_9
        if f5_latest == 1:
            if depth_arg == 1:
                f5_call_seq = f"{pos_1}"
            elif depth_arg == 2:
                f5_call_seq = f"{pos_2} -> {pos_1}"
            elif depth_arg == 3:
                f5_call_seq = f"{pos_3} -> {pos_2} -> {pos_1}"
            elif depth_arg == 4:
                f5_call_seq = f"{pos_4} -> {pos_3} -> {pos_2} -> {pos_1}"
            else:
                f5_call_seq = f"{pos_5} -> {pos_4} -> {pos_3} -> {pos_2} -> {pos_1}"
        elif f5_latest == 2:
            if depth_arg == 1:
                f5_call_seq = f"{pos_2}"
            elif depth_arg == 2:
                f5_call_seq = f"{pos_3} -> {pos_2}"
            elif depth_arg == 3:
                f5_call_seq = f"{pos_4} -> {pos_3} -> {pos_2}"
            elif depth_arg == 4:
                f5_call_seq = f"{pos_5} -> {pos_4} -> {pos_3} -> {pos_2}"
            else:
                f5_call_seq = f"{pos_6} -> {pos_5} -> {pos_4} -> {pos_3} -> {pos_2}"
        elif f5_latest == 3:
            if depth_arg == 1:
                f5_call_seq = f"{pos_3}"
            elif depth_arg == 2:
                f5_call_seq = f"{pos_4} -> {pos_3}"
            elif depth_arg == 3:
                f5_call_seq = f"{pos_5} -> {pos_4} -> {pos_3}"
            elif depth_arg == 4:
                f5_call_seq = f"{pos_6} -> {pos_5} -> {pos_4} -> {pos_3}"
            else:
                f5_call_seq = f"{pos_7} -> {pos_6} -> {pos_5} -> {pos_4} -> {pos_3}"
        elif f5_latest == 4:
            if depth_arg == 1:
                f5_call_seq = f"{pos_4}"
            elif depth_arg == 2:
                f5_call_seq = f"{pos_5} -> {pos_4}"
            elif depth_arg == 3:
                f5_call_seq = f"{pos_6} -> {pos_5} -> {pos_4}"
            elif depth_arg == 4:
                f5_call_seq = f"{pos_7} -> {pos_6} -> {pos_5} -> {pos_4}"
            else:
                f5_call_seq = f"{pos_8} -> {pos_7} -> {pos_6} -> {pos_5} -> {pos_4}"
        else:
            if depth_arg == 1:
                f5_call_seq = f"{pos_5}"
            elif depth_arg == 2:
                f5_call_seq = f"{pos_6} -> {pos_5}"
            elif depth_arg == 3:
                f5_call_seq = f"{pos_7} -> {pos_6} -> {pos_5}"
            elif depth_arg == 4:
                f5_call_seq = f"{pos_8} -> {pos_7} -> {pos_6} -> {pos_5}"
            else:
                f5_call_seq = f"{pos_9} -> {pos_8} -> {pos_7} -> {pos_6} -> {pos_5}"

        log_ver.add_pattern(pattern=f"{f5_entry_exit} entry: caller: {f5_call_seq}")
        log_ver.add_pattern(pattern=f"{f5_entry_exit} exit: return_value=None")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_no_parm2
    ####################################################################
    @pytest.mark.parametrize("latest_arg", (1, 2, 3, 4, 5))
    @pytest.mark.parametrize("depth_arg", (1, 2, 3, 4, 5))
    @pytest.mark.parametrize("f3_depth_arg", (1, 2, 3, 4))
    @pytest.mark.parametrize("f2_trace_enable_arg", (True, False))
    @pytest.mark.parametrize("f3_trace_enable_arg", (True, False))
    @etrace(log_ver=True)
    def test_etrace_on_nested_functions2(
        self,
        latest_arg: int,
        depth_arg: int,
        f3_depth_arg: int,
        f2_trace_enable_arg: bool,
        f3_trace_enable_arg: bool,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            latest_arg: latest arg for etrace
            depth_arg: depth arg for etrace
            f3_depth_arg: depth arg for etrace for f3
            f2_trace_enable_arg: specifies etrace enable for f2
            f3_trace_enable_arg: specifies etrace enable for f3
            caplog: pytest fixture to capture log output

        """
        f5_max_latest = 5
        if not f2_trace_enable_arg:
            f5_max_latest -= 1
        if not f3_trace_enable_arg:
            f5_max_latest -= 1
        f5_latest = min(f5_max_latest, latest_arg)

        @etrace(log_ver=self.log_ver)
        def f1() -> None:
            f2()

        @etrace(enable_trace=f2_trace_enable_arg, log_ver=self.log_ver)
        def f2() -> None:
            f3()

        @etrace(
            enable_trace=f3_trace_enable_arg, depth=f3_depth_arg, log_ver=self.log_ver
        )
        def f3() -> None:
            f4()

        @etrace(latest=latest_arg, log_ver=self.log_ver)
        def f4() -> None:
            f5()

        @etrace(latest=f5_latest, depth=depth_arg, log_ver=self.log_ver)
        def f5() -> None:
            pass

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        f1()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_nested_functions3
    ####################################################################
    @pytest.mark.parametrize("latest_arg", (1, 2, 3, 4, 5))
    @pytest.mark.parametrize("depth_arg", (1, 2, 3, 4, 5))
    @pytest.mark.parametrize("f3_depth_arg", (1, 2, 3, 4))
    @pytest.mark.parametrize("f2_trace_enable_arg", (True, False))
    @pytest.mark.parametrize("f3_trace_enable_arg", (True, False))
    def test_etrace_on_nested_functions3(
        self,
        latest_arg: int,
        depth_arg: int,
        f3_depth_arg: int,
        f2_trace_enable_arg: bool,
        f3_trace_enable_arg: bool,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            latest_arg: latest arg for etrace
            depth_arg: depth arg for etrace
            f3_depth_arg: depth arg for etrace for f3
            f2_trace_enable_arg: specifies etrace enable for f2
            f3_trace_enable_arg: specifies etrace enable for f3
            caplog: pytest fixture to capture log output

        """
        f5_max_latest = 5
        if not f2_trace_enable_arg:
            f5_max_latest -= 1
        if not f3_trace_enable_arg:
            f5_max_latest -= 1
        f5_latest = min(f5_max_latest, latest_arg)

        @etrace(omit_caller=True)
        def f1() -> None:
            f2()

        @etrace(enable_trace=f2_trace_enable_arg, omit_caller=True)
        def f2() -> None:
            f3()

        @etrace(enable_trace=f3_trace_enable_arg, omit_caller=True, depth=f3_depth_arg)
        def f3() -> None:
            f4()

        @etrace(omit_caller=True, latest=latest_arg)
        def f4() -> None:
            f5()

        @etrace(latest=f5_latest, depth=depth_arg, omit_caller=True)
        def f5() -> None:
            pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1()

        ################################################################
        # fn line numbers
        ################################################################
        f1_line_num = inspect.getsourcelines(f1)[1]
        f2_line_num = inspect.getsourcelines(f2)[1]
        f3_line_num = inspect.getsourcelines(f3)[1]
        f4_line_num = inspect.getsourcelines(f4)[1]
        f5_line_num = inspect.getsourcelines(f5)[1]

        ################################################################
        # fn entry/exit strings
        ################################################################
        f1_entry_exit = f"test_entry_trace.py::f1:{f1_line_num}"
        f2_entry_exit = f"test_entry_trace.py::f2:{f2_line_num}"
        f3_entry_exit = f"test_entry_trace.py::f3:{f3_line_num}"
        f4_entry_exit = f"test_entry_trace.py::f4:{f4_line_num}"
        f5_entry_exit = f"test_entry_trace.py::f5:{f5_line_num}"

        ################################################################
        # caller strings
        ################################################################
        ml_seq = (
            "test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_nested_functions:[0-9]+"
        )
        f1_seq = "test_entry_trace.py::f1:[0-9]+"
        f2_seq = "test_entry_trace.py::f2:[0-9]+"
        f3_seq = "test_entry_trace.py::f3:[0-9]+"
        f4_seq = "test_entry_trace.py::f4:[0-9]+"
        tw_seq = "entry_trace.py::trace_wrapper:[0-9]+"

        ################################################################
        # f1 expected trace results
        ################################################################
        f1_call_seq = f"{ml_seq}"
        log_ver.add_pattern(pattern=f"{f1_entry_exit} entry:")
        log_ver.add_pattern(pattern=f"{f1_entry_exit} exit: return_value=None")

        ################################################################
        # f2 expected trace results
        ################################################################
        f2_call_seq = f"{f1_seq}"
        if f2_trace_enable_arg:
            log_ver.add_pattern(pattern=f"{f2_entry_exit} entry:")
            log_ver.add_pattern(pattern=f"{f2_entry_exit} exit: return_value=None")

        ################################################################
        # f3 expected trace results
        ################################################################
        if f2_trace_enable_arg:
            pos_1 = f2_seq
            pos_2 = tw_seq
            pos_3 = f1_seq
            pos_4 = tw_seq
        else:
            pos_1 = f2_seq
            pos_2 = f1_seq
            pos_3 = tw_seq
            pos_4 = ml_seq

        if f3_depth_arg == 1:
            f3_call_seq = f"{pos_1}"
        elif f3_depth_arg == 2:
            f3_call_seq = f"{pos_2} -> {pos_1}"
        elif f3_depth_arg == 3:
            f3_call_seq = f"{pos_3} -> {pos_2} -> {pos_1}"
        else:
            f3_call_seq = f"{pos_4} -> {pos_3} -> {pos_2} -> {pos_1}"

        if f3_trace_enable_arg:
            log_ver.add_pattern(pattern=f"{f3_entry_exit} entry:")
            log_ver.add_pattern(pattern=f"{f3_entry_exit} exit: return_value=None")

        ################################################################
        # f4 expected trace results
        ################################################################
        pos_1 = f4_seq
        pos_2 = tw_seq
        pos_3 = f3_seq
        pos_4 = tw_seq
        pos_5 = f2_seq
        pos_6 = tw_seq
        pos_7 = f1_seq
        pos_8 = tw_seq
        pos_9 = ml_seq
        if not f3_trace_enable_arg:
            pos_4 = pos_5
            pos_5 = pos_6
            pos_6 = pos_7
            pos_7 = pos_8
            pos_8 = pos_9
        if not f2_trace_enable_arg:
            if not f3_trace_enable_arg:
                pos_5 = pos_6
            pos_6 = pos_7
            pos_7 = pos_8
            pos_8 = pos_9
        if latest_arg == 1:
            f4_call_seq = f"{pos_3}"
        elif latest_arg == 2:
            f4_call_seq = f"{pos_4}"
        elif latest_arg == 3:
            f4_call_seq = f"{pos_5}"
        elif latest_arg == 4:
            f4_call_seq = f"{pos_6}"
        else:
            f4_call_seq = f"{pos_7}"

        log_ver.add_pattern(pattern=f"{f4_entry_exit} entry:")
        log_ver.add_pattern(pattern=f"{f4_entry_exit} exit: return_value=None")

        ################################################################
        # f5 expected trace results
        ################################################################
        pos_1 = f4_seq
        pos_2 = tw_seq
        pos_3 = f3_seq
        pos_4 = tw_seq
        pos_5 = f2_seq
        pos_6 = tw_seq
        pos_7 = f1_seq
        pos_8 = tw_seq
        pos_9 = ml_seq
        if not f3_trace_enable_arg:
            pos_4 = pos_5
            pos_5 = pos_6
            pos_6 = pos_7
            pos_7 = pos_8
            pos_8 = pos_9
        if not f2_trace_enable_arg:
            if not f3_trace_enable_arg:
                pos_5 = pos_6
            pos_6 = pos_7
            pos_7 = pos_8
            pos_8 = pos_9
        if f5_latest == 1:
            if depth_arg == 1:
                f5_call_seq = f"{pos_1}"
            elif depth_arg == 2:
                f5_call_seq = f"{pos_2} -> {pos_1}"
            elif depth_arg == 3:
                f5_call_seq = f"{pos_3} -> {pos_2} -> {pos_1}"
            elif depth_arg == 4:
                f5_call_seq = f"{pos_4} -> {pos_3} -> {pos_2} -> {pos_1}"
            else:
                f5_call_seq = f"{pos_5} -> {pos_4} -> {pos_3} -> {pos_2} -> {pos_1}"
        elif f5_latest == 2:
            if depth_arg == 1:
                f5_call_seq = f"{pos_2}"
            elif depth_arg == 2:
                f5_call_seq = f"{pos_3} -> {pos_2}"
            elif depth_arg == 3:
                f5_call_seq = f"{pos_4} -> {pos_3} -> {pos_2}"
            elif depth_arg == 4:
                f5_call_seq = f"{pos_5} -> {pos_4} -> {pos_3} -> {pos_2}"
            else:
                f5_call_seq = f"{pos_6} -> {pos_5} -> {pos_4} -> {pos_3} -> {pos_2}"
        elif f5_latest == 3:
            if depth_arg == 1:
                f5_call_seq = f"{pos_3}"
            elif depth_arg == 2:
                f5_call_seq = f"{pos_4} -> {pos_3}"
            elif depth_arg == 3:
                f5_call_seq = f"{pos_5} -> {pos_4} -> {pos_3}"
            elif depth_arg == 4:
                f5_call_seq = f"{pos_6} -> {pos_5} -> {pos_4} -> {pos_3}"
            else:
                f5_call_seq = f"{pos_7} -> {pos_6} -> {pos_5} -> {pos_4} -> {pos_3}"
        elif f5_latest == 4:
            if depth_arg == 1:
                f5_call_seq = f"{pos_4}"
            elif depth_arg == 2:
                f5_call_seq = f"{pos_5} -> {pos_4}"
            elif depth_arg == 3:
                f5_call_seq = f"{pos_6} -> {pos_5} -> {pos_4}"
            elif depth_arg == 4:
                f5_call_seq = f"{pos_7} -> {pos_6} -> {pos_5} -> {pos_4}"
            else:
                f5_call_seq = f"{pos_8} -> {pos_7} -> {pos_6} -> {pos_5} -> {pos_4}"
        else:
            if depth_arg == 1:
                f5_call_seq = f"{pos_5}"
            elif depth_arg == 2:
                f5_call_seq = f"{pos_6} -> {pos_5}"
            elif depth_arg == 3:
                f5_call_seq = f"{pos_7} -> {pos_6} -> {pos_5}"
            elif depth_arg == 4:
                f5_call_seq = f"{pos_8} -> {pos_7} -> {pos_6} -> {pos_5}"
            else:
                f5_call_seq = f"{pos_9} -> {pos_8} -> {pos_7} -> {pos_6} -> {pos_5}"

        log_ver.add_pattern(pattern=f"{f5_entry_exit} entry:")
        log_ver.add_pattern(pattern=f"{f5_entry_exit} exit: return_value=None")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_nested_functions4
    ####################################################################
    @pytest.mark.parametrize("latest_arg", (1, 2, 3, 4, 5))
    @pytest.mark.parametrize("depth_arg", (1, 2, 3, 4, 5))
    @pytest.mark.parametrize("f3_depth_arg", (1, 2, 3, 4))
    @pytest.mark.parametrize("f2_trace_enable_arg", (True, False))
    @pytest.mark.parametrize("f3_trace_enable_arg", (True, False))
    @etrace(omit_caller=True, log_ver=True)
    def test_etrace_on_nested_functions4(
        self,
        latest_arg: int,
        depth_arg: int,
        f3_depth_arg: int,
        f2_trace_enable_arg: bool,
        f3_trace_enable_arg: bool,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            latest_arg: latest arg for etrace
            depth_arg: depth arg for etrace
            f3_depth_arg: depth arg for etrace for f3
            f2_trace_enable_arg: specifies etrace enable for f2
            f3_trace_enable_arg: specifies etrace enable for f3
            caplog: pytest fixture to capture log output

        """
        f5_max_latest = 5
        if not f2_trace_enable_arg:
            f5_max_latest -= 1
        if not f3_trace_enable_arg:
            f5_max_latest -= 1
        f5_latest = min(f5_max_latest, latest_arg)

        @etrace(log_ver=self.log_ver, omit_caller=True)
        def f1() -> None:
            f2()

        @etrace(
            enable_trace=f2_trace_enable_arg, omit_caller=True, log_ver=self.log_ver
        )
        def f2() -> None:
            f3()

        @etrace(
            omit_caller=True,
            enable_trace=f3_trace_enable_arg,
            depth=f3_depth_arg,
            log_ver=self.log_ver,
        )
        def f3() -> None:
            f4()

        @etrace(latest=latest_arg, omit_caller=True, log_ver=self.log_ver)
        def f4() -> None:
            f5()

        @etrace(
            omit_caller=True, latest=f5_latest, depth=depth_arg, log_ver=self.log_ver
        )
        def f5() -> None:
            pass

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        f1()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_one_parm
    ####################################################################
    def test_etrace_on_function_one_parm(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace
        def f1(a1: int) -> int:
            return a1

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1(42)

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: a1=42, "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_function_one_parm:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::f1:{f1_line_num} exit: " "return_value=42"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_one_parm2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_function_one_parm2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace(log_ver=self.log_ver)
        def f1(a1: int) -> int:
            return a1

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        f1(42)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_one_parm3
    ####################################################################
    def test_etrace_on_function_one_parm3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace(omit_caller=True)
        def f1(a1: int) -> int:
            return a1

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1(42)

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = rf"test_entry_trace.py::f1:{f1_line_num} entry: a1=42"

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::f1:{f1_line_num} exit: return_value=42"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_one_parm4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_function_one_parm4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace(omit_caller=True, log_ver=self.log_ver)
        def f1(a1: int) -> int:
            return a1

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        f1(42)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_args
    ####################################################################
    def test_etrace_on_function_args(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace
        def f1(*args: Any) -> str:
            ret_str = ""
            for arg in args:
                ret_str = f"{ret_str}{arg} "
            return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1(42, "forty_two", 83)

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: "
            r"args=\(42, 'forty_two', 83\), "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_function_args:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::f1:{f1_line_num} exit: "
            "return_value='42 forty_two 83 '"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_args2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_function_args2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        @etrace(log_ver=log_ver)
        def f1(*args: Any) -> str:
            ret_str = ""
            for arg in args:
                ret_str = f"{ret_str}{arg} "
            return ret_str

        ################################################################
        # mainline
        ################################################################
        f1(42, "forty_two", 83)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_args3
    ####################################################################
    def test_etrace_on_function_args3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace(omit_caller=True)
        def f1(*args: Any) -> str:
            ret_str = ""
            for arg in args:
                ret_str = f"{ret_str}{arg} "
            return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1(42, "forty_two", 83)

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: "
            r"args=\(42, 'forty_two', 83\)"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::f1:{f1_line_num} exit: "
            "return_value='42 forty_two 83 '"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_args4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_function_args4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        @etrace(log_ver=log_ver, omit_caller=True)
        def f1(*args: Any) -> str:
            ret_str = ""
            for arg in args:
                ret_str = f"{ret_str}{arg} "
            return ret_str

        ################################################################
        # mainline
        ################################################################
        f1(42, "forty_two", 83)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_kwargs
    ####################################################################
    def test_etrace_on_function_kwargs(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace
        def f1(**kwargs: Any) -> str:
            ret_str = ""
            for arg_name, arg_value in kwargs.items():
                ret_str = f"{ret_str}{arg_name}={arg_value} "
            return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1(kw1=42, kw2="forty_two", kw3=83)

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: "
            "kw1=42, kw2='forty_two', kw3=83, "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_function_kwargs:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::f1:{f1_line_num} exit: return_value='kw1=42 "
            f"kw2=forty_two kw3=83 '"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_kwargs2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_function_kwargs2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        @etrace(log_ver=log_ver)
        def f1(**kwargs: Any) -> str:
            ret_str = ""
            for arg_name, arg_value in kwargs.items():
                ret_str = f"{ret_str}{arg_name}={arg_value} "
            return ret_str

        ################################################################
        # mainline
        ################################################################
        f1(kw1=42, kw2="forty_two", kw3=83)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_kwargs3
    ####################################################################
    def test_etrace_on_function_kwargs3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace(omit_caller=True)
        def f1(**kwargs: Any) -> str:
            ret_str = ""
            for arg_name, arg_value in kwargs.items():
                ret_str = f"{ret_str}{arg_name}={arg_value} "
            return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1(kw1=42, kw2="forty_two", kw3=83)

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: "
            "kw1=42, kw2='forty_two', kw3=83"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::f1:{f1_line_num} exit: return_value='kw1=42 "
            f"kw2=forty_two kw3=83 '"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_kwargs4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_function_kwargs4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        @etrace(log_ver=log_ver, omit_caller=True)
        def f1(**kwargs: Any) -> str:
            ret_str = ""
            for arg_name, arg_value in kwargs.items():
                ret_str = f"{ret_str}{arg_name}={arg_value} "
            return ret_str

        ################################################################
        # mainline
        ################################################################
        f1(kw1=42, kw2="forty_two", kw3=83)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_pos_args
    ####################################################################
    def test_etrace_on_function_pos_args(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace
        def f1(a1: int, *args: Any) -> str:
            ret_str = f"{a1} "
            for arg in args:
                ret_str = f"{ret_str}{arg} "
            return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1(42, "forty_two", 83)

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: "
            r"a1=42, args=\('forty_two', 83\), "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_function_pos_args:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::f1:{f1_line_num} exit: "
            f"return_value='42 forty_two 83 '"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_pos_args2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_function_pos_args2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        @etrace(log_ver=log_ver)
        def f1(a1: int, *args: Any) -> str:
            ret_str = f"{a1} "
            for arg in args:
                ret_str = f"{ret_str}{arg} "
            return ret_str

        ################################################################
        # mainline
        ################################################################
        f1(42, "forty_two", 83)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_pos_args3
    ####################################################################
    def test_etrace_on_function_pos_args3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """

        @etrace(omit_caller=True)
        def f1(a1: int, *args: Any) -> str:
            ret_str = f"{a1} "
            for arg in args:
                ret_str = f"{ret_str}{arg} "
            return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        f1(42, "forty_two", 83)

        f1_line_num = inspect.getsourcelines(f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::f1:{f1_line_num} entry: "
            r"a1=42, args=\('forty_two', 83\)"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::f1:{f1_line_num} exit: "
            f"return_value='42 forty_two 83 '"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_function_pos_args4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_function_pos_args4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        @etrace(log_ver=log_ver, omit_caller=True)
        def f1(a1: int, *args: Any) -> str:
            ret_str = f"{a1} "
            for arg in args:
                ret_str = f"{ret_str}{arg} "
            return ret_str

        ################################################################
        # mainline
        ################################################################
        f1(42, "forty_two", 83)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_no_parm
    ####################################################################
    def test_etrace_on_method_no_parm(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace
            def f1(self) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1().f1()

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_method_no_parm:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_no_parm2a
    ####################################################################
    def test_etrace_on_method_no_parm2a(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=True)
            def f1(self) -> None:
                pass

        ################################################################
        # mainline
        ################################################################

        t1 = Test1()
        t1.f1()

        log_ver = t1.log_ver

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_no_parm2b
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_method_no_parm2b(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            @etrace(log_ver=log_ver)
            def f1(self) -> None:
                pass

        ################################################################
        # mainline
        ################################################################

        t1 = Test1()
        t1.f1()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_no_parm3
    ####################################################################
    def test_etrace_on_method_no_parm3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True)
            def f1(self) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1().f1()

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry:"

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_no_parm4a
    ####################################################################
    def test_etrace_on_method_no_parm4a(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=True, omit_caller=True)
            def f1(self) -> None:
                pass

        ################################################################
        # mainline
        ################################################################

        t1 = Test1()
        t1.f1()

        log_ver = t1.log_ver

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_no_parm4b
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_method_no_parm4b(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            @etrace(log_ver=log_ver, omit_caller=True)
            def f1(self) -> None:
                pass

        ################################################################
        # mainline
        ################################################################

        t1 = Test1()
        t1.f1()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_one_parm
    ####################################################################
    def test_etrace_on_method_one_parm(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace
            def f1(self, a1: int) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1().f1(42)

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: a1=42, "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_method_one_parm:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_one_parm2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_method_one_parm2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=self.log_ver)
            def f1(self, a1: int) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        Test1().f1(42)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_one_parm3
    ####################################################################
    def test_etrace_on_method_one_parm3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True)
            def f1(self, a1: int) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1().f1(42)

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: a1=42"

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_one_parm4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_method_one_parm4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True, log_ver=self.log_ver)
            def f1(self, a1: int) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        Test1().f1(42)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_one_parm
    ####################################################################
    def test_etrace_on_method_args(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace
            def f1(self, *args: Any) -> str:
                ret_str = ""
                for arg in args:
                    ret_str = f"{ret_str}{arg} "
                return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1().f1(42, "forty_two", 83)

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: "
            r"args=\(42, 'forty_two', 83\), "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_method_args:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: "
            "return_value='42 forty_two 83 '"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_one_parm2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_method_args2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=self.log_ver)
            def f1(self, *args: Any) -> str:
                ret_str = ""
                for arg in args:
                    ret_str = f"{ret_str}{arg} "
                return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        Test1().f1(42, "forty_two", 83)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_one_parm3
    ####################################################################
    def test_etrace_on_method_args3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True)
            def f1(self, *args: Any) -> str:
                ret_str = ""
                for arg in args:
                    ret_str = f"{ret_str}{arg} "
                return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1().f1(42, "forty_two", 83)

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: "
            r"args=\(42, 'forty_two', 83\)"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: "
            "return_value='42 forty_two 83 '"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_method_one_parm4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_method_args4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=self.log_ver, omit_caller=True)
            def f1(self, *args: Any) -> str:
                ret_str = ""
                for arg in args:
                    ret_str = f"{ret_str}{arg} "
                return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        Test1().f1(42, "forty_two", 83)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_static_method_no_parm
    ####################################################################
    def test_etrace_on_static_method_no_parm(
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
            def f1() -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1().f1()

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_static_method_no_parm:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_static_method_no_parm2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_static_method_no_parm2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a static method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            @etrace(log_ver=self.log_ver)
            @staticmethod
            def f1() -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        Test1().f1()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_static_method_no_parm3
    ####################################################################
    def test_etrace_on_static_method_no_parm3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a static method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True)
            @staticmethod
            def f1() -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1().f1()

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry:"

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_static_method_no_parm4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_static_method_no_parm4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a static method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            @etrace(log_ver=log_ver, omit_caller=True)
            @staticmethod
            def f1() -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        Test1().f1()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_static_method_one_parm
    ####################################################################
    def test_etrace_on_static_method_one_parm(
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
            def f1(a1: str) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1().f1("42")

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: a1='42', "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_static_method_one_parm:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_static_method_one_parm2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_static_method_one_parm2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a static method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            @etrace(log_ver=log_ver)
            @staticmethod
            def f1(a1: str) -> None:
                pass

        ################################################################
        # mainline
        ################################################################

        Test1().f1("42")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_static_method_one_parm3
    ####################################################################
    def test_etrace_on_static_method_one_parm3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a static method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True)
            @staticmethod
            def f1(a1: str) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1().f1("42")

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: a1='42'"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_static_method_one_parm4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_static_method_one_parm4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a static method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            @etrace(log_ver=log_ver, omit_caller=True)
            @staticmethod
            def f1(a1: str) -> None:
                pass

        ################################################################
        # mainline
        ################################################################

        Test1().f1("42")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_static_method_args
    ####################################################################
    def test_etrace_on_static_method_args(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace
            @staticmethod
            def f1(*args: Any) -> str:
                ret_str = ""
                for arg in args:
                    ret_str = f"{ret_str}{arg} "
                return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1().f1(42, "forty_two", 83)

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: "
            r"args=\(42, 'forty_two', 83\), "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_static_method_args:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: "
            "return_value='42 forty_two 83 '"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_static_method_args2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_static_method_args2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            @etrace(log_ver=log_ver)
            @staticmethod
            def f1(*args: Any) -> str:
                ret_str = ""
                for arg in args:
                    ret_str = f"{ret_str}{arg} "
                return ret_str

        ################################################################
        # mainline
        ################################################################
        Test1().f1(42, "forty_two", 83)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_static_method_args3
    ####################################################################
    def test_etrace_on_static_method_args3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True)
            @staticmethod
            def f1(*args: Any) -> str:
                ret_str = ""
                for arg in args:
                    ret_str = f"{ret_str}{arg} "
                return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1().f1(42, "forty_two", 83)

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: "
            r"args=\(42, 'forty_two', 83\)"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: "
            "return_value='42 forty_two 83 '"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_static_method_args2
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_static_method_args2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            @etrace(log_ver=log_ver, omit_caller=True)
            @staticmethod
            def f1(*args: Any) -> str:
                ret_str = ""
                for arg in args:
                    ret_str = f"{ret_str}{arg} "
                return ret_str

        ################################################################
        # mainline
        ################################################################
        Test1().f1(42, "forty_two", 83)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_method_no_parm
    ####################################################################
    def test_etrace_on_class_method_no_parm(
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
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1.f1()

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_class_method_no_parm:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_method_no_parm2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_class_method_no_parm2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            @etrace(log_ver=log_ver)
            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################

        Test1.f1()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_method_no_parm3
    ####################################################################
    def test_etrace_on_class_method_no_parm3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True)
            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1.f1()

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry:"

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_method_no_parm4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_class_method_no_parm4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            @etrace(log_ver=log_ver, omit_caller=True)
            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################

        Test1.f1()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_method_one_parm
    ####################################################################
    def test_etrace_on_class_method_one_parm(
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
            def f1(cls, v1: float) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1.f1(1.1)

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: v1=1.1, "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_class_method_one_parm:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_method_one_parm2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_class_method_one_parm2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            @etrace(log_ver=log_ver)
            @classmethod
            def f1(cls, v1: float) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        Test1.f1(1.1)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_method_one_parm3
    ####################################################################
    def test_etrace_on_class_method_one_parm3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True)
            @classmethod
            def f1(cls, v1: float) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1.f1(1.1)

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: v1=1.1"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_method_one_parm4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_class_method_one_parm4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            @etrace(log_ver=log_ver, omit_caller=True)
            @classmethod
            def f1(cls, v1: float) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        Test1.f1(1.1)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_method_args
    ####################################################################
    def test_etrace_on_class_method_args(
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
            def f1(cls, *args: Any) -> str:
                ret_str = ""
                for arg in args:
                    ret_str = f"{ret_str}{arg} "
                return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1.f1(42, "forty_two", 83)

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: "
            r"args=\(42, 'forty_two', 83\), "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_class_method_args:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: "
            "return_value='42 forty_two 83 '"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_method_args2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_class_method_args2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=self.log_ver)
            @classmethod
            def f1(cls, *args: Any) -> str:
                ret_str = ""
                for arg in args:
                    ret_str = f"{ret_str}{arg} "
                return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        Test1.f1(42, "forty_two", 83)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_method_args3
    ####################################################################
    def test_etrace_on_class_method_args3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True)
            @classmethod
            def f1(cls, *args: Any) -> str:
                ret_str = ""
                for arg in args:
                    ret_str = f"{ret_str}{arg} "
                return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1.f1(42, "forty_two", 83)

        f1_line_num = inspect.getsourcelines(Test1.f1)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.f1:{f1_line_num} entry: "
            r"args=\(42, 'forty_two', 83\)"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.f1:{f1_line_num} exit: "
            "return_value='42 forty_two 83 '"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_method_args4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_class_method_args4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=self.log_ver, omit_caller=True)
            @classmethod
            def f1(cls, *args: Any) -> str:
                ret_str = ""
                for arg in args:
                    ret_str = f"{ret_str}{arg} "
                return ret_str

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        Test1.f1(42, "forty_two", 83)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_init_method_no_parm
    ####################################################################
    def test_etrace_on_class_init_method_no_parm(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace
            def __init__(self) -> None:
                self.v1 = 1

            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1()

        f1_line_num = inspect.getsourcelines(Test1.__init__)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.__init__:{f1_line_num} entry: "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_class_init_method_no_parm:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.__init__:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_init_method_no_parm2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_class_init_method_no_parm2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=self.log_ver)
            def __init__(self) -> None:
                self.v1 = 1

            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        Test1()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_init_method_no_parm3
    ####################################################################
    def test_etrace_on_class_init_method_no_parm3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True)
            def __init__(self) -> None:
                self.v1 = 1

            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1()

        f1_line_num = inspect.getsourcelines(Test1.__init__)[1]
        exp_entry_log_msg = rf"test_entry_trace.py::Test1.__init__:{f1_line_num} entry:"

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.__init__:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_init_method_no_parm4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_class_init_method_no_parm4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=self.log_ver, omit_caller=True)
            def __init__(self) -> None:
                self.v1 = 1

            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        Test1()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_init_method_one_parm
    ####################################################################
    def test_etrace_on_class_init_method_one_parm(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace
            def __init__(self, v1: int) -> None:
                self.v1 = v1

            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1(42)

        f1_line_num = inspect.getsourcelines(Test1.__init__)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.__init__:{f1_line_num} entry: v1=42, "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_class_init_method_one_parm:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.__init__:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_init_method_one_parm2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_class_init_method_one_parm2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=self.log_ver)
            def __init__(self, v1: int) -> None:
                self.v1 = v1

            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        Test1(42)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_init_method_one_parm3
    ####################################################################
    def test_etrace_on_class_init_method_one_parm3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True)
            def __init__(self, v1: int) -> None:
                self.v1 = v1

            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        Test1(42)

        f1_line_num = inspect.getsourcelines(Test1.__init__)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.__init__:{f1_line_num} entry: v1=42"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.__init__:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_init_method_one_parm4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_class_init_method_one_parm4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=self.log_ver, omit_caller=True)
            def __init__(self, v1: int) -> None:
                self.v1 = v1

            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        Test1(42)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_init_method_args
    ####################################################################
    def test_etrace_on_class_init_method_args(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace
            def __init__(self, *args: Any) -> None:
                self.args_str = ""
                for arg in args:
                    self.args_str = f"{self.args_str}{arg} "

            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        t1 = Test1(42, "forty_two", 83)

        f1_line_num = inspect.getsourcelines(Test1.__init__)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.__init__:{f1_line_num} entry: "
            r"args=\(42, 'forty_two', 83\), "
            "caller: test_entry_trace.py::TestEntryTraceBasic."
            "test_etrace_on_class_init_method_args:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.__init__:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)

        assert t1.args_str == "42 forty_two 83 "
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_init_method_args2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_class_init_method_args2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=self.log_ver)
            def __init__(self, *args: Any) -> None:
                self.args_str = ""
                for arg in args:
                    self.args_str = f"{self.args_str}{arg} "

            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        t1 = Test1(42, "forty_two", 83)

        assert t1.args_str == "42 forty_two 83 "
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_init_method_args3
    ####################################################################
    def test_etrace_on_class_init_method_args3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(omit_caller=True)
            def __init__(self, *args: Any) -> None:
                self.args_str = ""
                for arg in args:
                    self.args_str = f"{self.args_str}{arg} "

            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")
        t1 = Test1(42, "forty_two", 83)

        f1_line_num = inspect.getsourcelines(Test1.__init__)[1]
        exp_entry_log_msg = (
            rf"test_entry_trace.py::Test1.__init__:{f1_line_num} entry: "
            r"args=\(42, 'forty_two', 83\)"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"test_entry_trace.py::Test1.__init__:{f1_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)

        assert t1.args_str == "42 forty_two 83 "
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_class_init_method_args4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_class_init_method_args4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """

        class Test1:
            @etrace(log_ver=self.log_ver, omit_caller=True)
            def __init__(self, *args: Any) -> None:
                self.args_str = ""
                for arg in args:
                    self.args_str = f"{self.args_str}{arg} "

            @classmethod
            def f1(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = self.log_ver
        t1 = Test1(42, "forty_two", 83)

        assert t1.args_str == "42 forty_two 83 "
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_with_log_ver
    ####################################################################
    def test_etrace_on_with_log_ver(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")

        class Test1:
            def __init__(self, *args: Any, a_log_ver: LogVer) -> None:
                self.args_str = ""
                for arg in args:
                    self.args_str = f"{self.args_str}{arg} "
                self.log_ver = a_log_ver

            @etrace(log_ver=log_ver)
            def f1(self, a: int, b: str = "forty-two") -> str:
                return f"{a=}, {b=}, {self.args_str=}"

        ################################################################
        # mainline
        ################################################################

        t1 = Test1(42, "forty_two", 83, a_log_ver=log_ver)

        assert t1.args_str == "42 forty_two 83 "

        t1.f1(84, b="eighty-four")
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_with_log_ver2
    ####################################################################
    @etrace(log_ver=True)
    def test_etrace_on_with_log_ver2(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            def __init__(self, *args: Any, a_log_ver: LogVer) -> None:
                self.args_str = ""
                for arg in args:
                    self.args_str = f"{self.args_str}{arg} "
                self.log_ver = a_log_ver

            @etrace(log_ver=log_ver)
            def f1(self, a: int, b: str = "forty-two") -> str:
                return f"{a=}, {b=}, {self.args_str=}"

        ################################################################
        # mainline
        ################################################################

        t1 = Test1(42, "forty_two", 83, a_log_ver=log_ver)

        assert t1.args_str == "42 forty_two 83 "

        t1.f1(84, b="eighty-four")
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_with_log_ver3
    ####################################################################
    def test_etrace_on_with_log_ver3(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")

        class Test1:
            def __init__(self, *args: Any, a_log_ver: LogVer) -> None:
                self.args_str = ""
                for arg in args:
                    self.args_str = f"{self.args_str}{arg} "
                self.log_ver = a_log_ver

            @etrace(log_ver=log_ver, omit_caller=True)
            def f1(self, a: int, b: str = "forty-two") -> str:
                return f"{a=}, {b=}, {self.args_str=}"

        ################################################################
        # mainline
        ################################################################

        t1 = Test1(42, "forty_two", 83, a_log_ver=log_ver)

        assert t1.args_str == "42 forty_two 83 "

        t1.f1(84, b="eighty-four")
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_on_with_log_ver4
    ####################################################################
    @etrace(log_ver=True, omit_caller=True)
    def test_etrace_on_with_log_ver4(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a class method.

        Args:
            caplog: pytest fixture to capture log output

        """
        log_ver = self.log_ver

        class Test1:
            def __init__(self, *args: Any, a_log_ver: LogVer) -> None:
                self.args_str = ""
                for arg in args:
                    self.args_str = f"{self.args_str}{arg} "
                self.log_ver = a_log_ver

            @etrace(log_ver=log_ver, omit_caller=True)
            def f1(self, a: int, b: str = "forty-two") -> str:
                return f"{a=}, {b=}, {self.args_str=}"

        ################################################################
        # mainline
        ################################################################

        t1 = Test1(42, "forty_two", 83, a_log_ver=log_ver)

        assert t1.args_str == "42 forty_two 83 "

        t1.f1(84, b="eighty-four")
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)


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
args_list = (1, 2.2, "three", [4, 4.4, "four", (4,)])

p_args_list = (
    ("a1", "one"),
    ("a2", 222),
    ("a3", "thrace"),
    ("a4", ["four", "for", 44.44, ("426",)]),
)

kwargs_list = (
    ("kw1", 1),
    ("kw2", 2.2),
    ("kw3", "three"),
    ("kw4", [4, 4.4, "four", (4,)]),
)


@pytest.mark.cover2
class TestEntryTraceCombos:
    """Test EntryTrace with various combinations."""

    ####################################################################
    # test_etrace_combo_signature
    ####################################################################
    @pytest.mark.parametrize("num_po_arg", [0, 1, 2, 3])
    @pytest.mark.parametrize("num_pk_arg", [0, 1, 2, 3])
    @pytest.mark.parametrize("num_ko_arg", [0, 1, 2, 3])
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

        print(
            f"test_etrace_combo_signature entered: {num_po_arg=}, {num_pk_arg=}, "
            f"{num_ko_arg=}"
        )
        log_ver = LogVer()

        @dataclass
        class ArgSpecRetRes:
            arg_spec: str = ""
            log_result: str = ""
            ret_result: str = ""

            def __add__(self, other: "ArgSpecRetRes") -> "ArgSpecRetRes":
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

            def __add__(self, other: "OmitVariation") -> "OmitVariation":
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

            def __add__(self, other: "PlistSection") -> "PlistSection":
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
            ) -> None:
                self.num_po = num_po
                self.num_pk = num_pk
                self.num_ko = num_ko

                self.raw_po_parms: list[str] = list(
                    self.raw_parms[PlistType.Po][0:num_po]
                )
                self.raw_pk_parms: list[str] = list(
                    self.raw_parms[PlistType.Pk][0:num_pk]
                )
                self.raw_ko_parms: list[str] = list(
                    self.raw_parms[PlistType.Ko][0:num_ko]
                )

                self.ret_stmt: str = "".join(
                    list(
                        map(
                            self.set_ret_stmt,
                            self.raw_po_parms + self.raw_pk_parms + self.raw_ko_parms,
                        )
                    )
                )

                self.po_pk_raw_arg_specs = self.build_po_pk_arg_specs(num_pk=num_pk)

                self.ko_raw_arg_specs = [list(map(self.set_ko_args, self.raw_ko_parms))]

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

            def build_po_pk_arg_specs(self, num_pk: int) -> list[list[str]]:
                po_raw_arg_spec: list[list[str]] = [
                    list(map(self.set_po_args, self.raw_po_parms))
                ]

                pk_raw_arg_specs: list[list[str]] | Iterator[list[str]] = (
                    self.build_pk_arg_specs(num_pk=num_pk)
                )

                pre_raw_arg_specs: list[tuple[list[str], list[str]]] = list(
                    it.product(po_raw_arg_spec, pk_raw_arg_specs)
                )

                specs: list[list[str]] = [
                    spec_item[0] + spec_item[1] for spec_item in pre_raw_arg_specs
                ]

                return specs

            def build_pk_arg_specs(
                self, num_pk: int
            ) -> list[list[str]] | Iterator[list[str]]:
                arg_spec: list[list[str]] | Iterator[list[str]] = [[]]
                if num_pk:
                    p_or_k_array: list[int] = [0] * num_pk + [1] * num_pk

                    arg_spec = map(
                        self.do_pk_args, mi.sliding_window(p_or_k_array, num_pk)
                    )
                return arg_spec

            def build_plist_section(
                self,
                plist_parms: list[str],
                raw_arg_specs: list[list[str]],
                prefix_idx: int,
                suffix_idx: int,
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

            def do_pk_args(self, p_or_k_array: tuple[int, ...]) -> list[str]:
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
                    # print(f"{omit_parm_parts=}")
                    if omit_parm_parts:
                        omit_parms = list(omit_parm_parts)
                    else:
                        omit_parms = []

                    # print(f"55 {omit_parms=}")
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

                    arg_specs_ret_reses: list[Iterable[ArgSpecRetRes]] = list(
                        map(
                            do_star_arg_spec2,
                            mi.sliding_window(arg_spec_array, len(def_list)),
                        )
                    )

                    final_arg_specs: list[ArgSpecRetRes] = []
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
                omit_parm_parts: tuple[str, ...],
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

                def get_perms(raw_arg_spec: list[str]) -> list[str]:
                    arg_spec_parts = list(
                        it.starmap(self.set_arg_spec, zip(raw_arg_spec, arg_spec_array))
                    )

                    left_args2, after_args = mi.before_and_after(
                        lambda x: "=" not in x, arg_spec_parts
                    )
                    mid_args, right_args2 = mi.before_and_after(
                        lambda x: "=" in x, after_args
                    )

                    if len(mid_args_list := list(mid_args)) > 1:
                        return list(
                            map(
                                lambda x: "".join(
                                    list(left_args2) + list(x) + list(right_args2)
                                ),
                                it.permutations(mid_args_list),
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
            def set_arg_spec(parm: str, selector: int) -> str:
                return ("", parm)[selector]

            @staticmethod
            def set_defaults(parm: str, selector: int) -> str:
                return parm + ("", ", ", f"={parm[-1]}, ")[selector]

            @staticmethod
            def set_po_args(parm: str) -> str:
                return f"{parm[-1]}0, "

            @staticmethod
            def set_pk_args(parm: str, selector: int) -> str:
                return (f"{parm[-1]}0, ", f"{parm}={parm[-1]}0, ")[selector]

            @staticmethod
            def set_ko_args(parm: str) -> str:
                return f"{parm}={parm[-1]}0, "

            @staticmethod
            def set_ret_result(parm: str, selector: int) -> str:
                return (f"{parm}={parm[-1]}, ", f"{parm}={parm[-1]}0, ")[selector]

            @staticmethod
            def set_ret_stmt(parm: str) -> str:
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

                exec(code)

                for idx2, arg_spec_ret_res in enumerate(
                    omit_variation.arg_specs_ret_reses
                ):
                    exec(f"f999({arg_spec_ret_res.arg_spec})")

                    exp_entry_log_msg = (
                        rf"<string>::f1:\? entry: {arg_spec_ret_res.log_result}"
                        "caller: <string>:1"
                    )

                    log_ver.add_pattern(
                        level=logging.DEBUG,
                        pattern=exp_entry_log_msg,
                        log_name="scottbrian_utils.entry_trace",
                        fullmatch=True,
                    )

                    exp_exit_log_msg = (
                        rf"<string>::f1:\? exit: return_value='"
                        rf"{arg_spec_ret_res.ret_result}'"
                    )

                    log_ver.add_pattern(
                        level=logging.DEBUG,
                        pattern=exp_exit_log_msg,
                        log_name="scottbrian_utils.entry_trace",
                        fullmatch=True,
                    )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

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
        def f1() -> None:
            pass

        class Caller:
            def __init__(self) -> None:
                if caller_type_arg == FunctionType.InitMethod:
                    target_rtn()

            def caller(self) -> None:
                target_rtn()

            @staticmethod
            def static_caller() -> None:
                target_rtn()

            @classmethod
            def class_caller(cls) -> None:
                target_rtn()

        class Target:
            @etrace(enable_trace=trace_enabled)
            def __init__(self) -> None:
                pass

            @etrace
            def target(self) -> None:
                pass

            @etrace
            @staticmethod
            def static_target() -> None:
                pass

            @etrace
            @classmethod
            def class_target(cls) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()

        file_name = "test_entry_trace.py"

        ################################################################
        # choose the target function or method
        ################################################################
        target_rtn: Callable[[], None] | type[Target]
        if target_type_arg == FunctionType.Function:
            target_rtn = f1
            target_line_num = inspect.getsourcelines(f1)[1]
            target_qual_name = "::f1"

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
            rf"{file_name}{target_qual_name}:{target_line_num} entry: "
            f"caller: {file_name}::{caller_qual_name}:[0-9]+"
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        exp_exit_log_msg = (
            f"{file_name}{target_qual_name}:{target_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_combo_parms
    ####################################################################
    args_to_use = map(lambda n: args_list[0:n], range(len(args_list) + 1))
    kwargs_to_use = map(lambda n: dict(kwargs_list[0:n]), range(len(kwargs_list) + 1))

    @pytest.mark.parametrize("caller_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("target_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("args_arg", args_to_use)
    @pytest.mark.parametrize("kwargs_arg", kwargs_to_use)
    def test_etrace_combo_parms(
        self,
        caller_type_arg: FunctionType,
        target_type_arg: FunctionType,
        args_arg: list[Any],
        kwargs_arg: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caller_type_arg: type of function that makes the call
            target_type_arg: type of function that is called
            args_arg: list of args to use on calls being traced
            kwargs_arg: dict of kwargs to use on calls being traced
            caplog: pytest fixture to capture log output

        """
        if target_type_arg == FunctionType.InitMethod:
            trace_enabled = True
        else:
            trace_enabled = False

        @etrace
        def f1(*args: tuple[Any], **kwargs: dict[str, Any]) -> None:
            pass

        class Caller:
            def __init__(self) -> None:
                if caller_type_arg == FunctionType.InitMethod:
                    target_rtn(*args_arg, **kwargs_arg)

            def caller(self) -> None:
                target_rtn(*args_arg, **kwargs_arg)

            @staticmethod
            def static_caller() -> None:
                target_rtn(*args_arg, **kwargs_arg)

            @classmethod
            def class_caller(cls) -> None:
                target_rtn(*args_arg, **kwargs_arg)

        class Target:
            @etrace(enable_trace=trace_enabled)
            def __init__(self, *args: tuple[Any], **kwargs: dict[str, Any]) -> None:
                pass

            @etrace
            def target(self, *args: tuple[Any], **kwargs: dict[str, Any]) -> None:
                pass

            @etrace
            @staticmethod
            def static_target(*args: tuple[Any], **kwargs: dict[str, Any]) -> None:
                pass

            @etrace
            @classmethod
            def class_target(cls, *args: tuple[Any], **kwargs: dict[str, Any]) -> None:
                pass

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer()

        file_name = "test_entry_trace.py"

        ################################################################
        # choose the target function or method
        ################################################################
        target_rtn: Callable[[], None] | type[Target]
        if target_type_arg == FunctionType.Function:
            target_rtn = f1
            target_line_num = inspect.getsourcelines(f1)[1]
            target_qual_name = "::f1"

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
            target_rtn(*args_arg, **kwargs_arg)
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

        if args_arg:
            args_str = f" args={re.escape(str(args_arg))},"
        else:
            args_str = ""

        kwargs_str = " "
        for key, val in kwargs_arg.items():
            if isinstance(val, str):
                kwargs_str += f"{key}='{val}', "
            else:
                kwargs_str += f"{key}={val}, "

        kwargs_str = re.escape(kwargs_str)

        exp_entry_log_msg = (
            rf"{file_name}{target_qual_name}:{target_line_num} entry:{args_str}"
            f"{kwargs_str}"
            f"caller: {file_name}::{caller_qual_name}:[0-9]+"
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_entry_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )

        exp_exit_log_msg = (
            f"{file_name}{target_qual_name}:{target_line_num} exit: return_value=None"
        )

        log_ver.add_pattern(
            level=logging.DEBUG,
            pattern=exp_exit_log_msg,
            log_name="scottbrian_utils.entry_trace",
            fullmatch=True,
        )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_combo_omits
    ####################################################################
    args_to_use = map(lambda n: args_list[0:n], range(len(args_list) + 1))
    kwargs_to_use = map(lambda n: dict(kwargs_list[0:n]), range(len(kwargs_list) + 1))

    kwargs_and_omits = it.chain.from_iterable(
        map(
            lambda kwdict: it.product([kwdict], mi.powerset(kwdict.keys())),
            kwargs_to_use,
        )
    )

    @pytest.mark.parametrize("caller_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("target_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("args_arg", args_to_use)
    @pytest.mark.parametrize("omit_args_arg", (True, False))
    @pytest.mark.parametrize("kwargs_and_omits_arg", kwargs_and_omits)
    @pytest.mark.parametrize("omit_ret_val_arg", (True, False))
    def test_etrace_combo_omits(
        self,
        caller_type_arg: FunctionType,
        target_type_arg: FunctionType,
        args_arg: tuple[Any],
        omit_args_arg: bool,
        kwargs_and_omits_arg: tuple[dict[str, Any], tuple[str]],
        omit_ret_val_arg: bool,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        Args:
            caller_type_arg: type of function that makes the call
            target_type_arg: type of function to be called
            args_arg: tuple of args to use on the calls that are traced
            omit_args_arg: if true bool, don't trace args
            kwargs_and_omits_arg: dict and list of omits
            omit_ret_val_arg: if True, omit ret value fro exit trace
            caplog: pytest fixture to capture log output

        """
        if target_type_arg == FunctionType.InitMethod:
            trace_enabled = True
        else:
            trace_enabled = False

        kwargs_arg = kwargs_and_omits_arg[0]
        omit_kwargs_arg = list(kwargs_and_omits_arg[1])

        omit_parms_list: list[str] = omit_kwargs_arg.copy()
        if omit_args_arg:
            omit_parms_list.append("args")

        if "kw2" in kwargs_arg and target_type_arg != FunctionType.InitMethod:
            ret_kw2 = True
        else:
            ret_kw2 = False

        @etrace(
            omit_parms=omit_parms_list,
            omit_return_value=omit_ret_val_arg,
        )
        def f1(*args: tuple[Any], **kwargs: dict[str, Any]) -> Any:
            if ret_kw2:
                return kwargs["kw2"]

        class Caller:
            def __init__(self) -> None:
                if caller_type_arg == FunctionType.InitMethod:
                    target_rtn(*args_arg, **kwargs_arg)

            def caller(self) -> None:
                target_rtn(*args_arg, **kwargs_arg)

            @staticmethod
            def static_caller() -> None:
                target_rtn(*args_arg, **kwargs_arg)

            @classmethod
            def class_caller(cls) -> None:
                target_rtn(*args_arg, **kwargs_arg)

        class Target:
            @etrace(
                enable_trace=trace_enabled,
                omit_parms=omit_parms_list,
                omit_return_value=omit_ret_val_arg,
            )
            def __init__(self, *args: tuple[Any], **kwargs: dict[str, Any]) -> None:
                pass

            @etrace(
                omit_parms=omit_parms_list,
                omit_return_value=omit_ret_val_arg,
            )
            def target(self, *args: tuple[Any], **kwargs: dict[str, Any]) -> Any:
                if ret_kw2:
                    return kwargs["kw2"]

            @etrace(
                omit_parms=omit_parms_list,
                omit_return_value=omit_ret_val_arg,
            )
            @staticmethod
            def static_target(*args: tuple[Any], **kwargs: dict[str, Any]) -> Any:
                if ret_kw2:
                    return kwargs["kw2"]

            @etrace(
                omit_parms=omit_parms_list,
                omit_return_value=omit_ret_val_arg,
            )
            @classmethod
            def class_target(cls, *args: tuple[Any], **kwargs: dict[str, Any]) -> Any:
                if ret_kw2:
                    return kwargs["kw2"]

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")

        file_name = "test_entry_trace.py"

        ################################################################
        # choose the target function or method
        ################################################################
        if target_type_arg == FunctionType.Function:
            target_rtn = f1
            target_line_num = inspect.getsourcelines(f1)[1]
            target_qual_name = "::f1"

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
            target_rtn(*args_arg, **kwargs_arg)
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

        if omit_args_arg:
            args_str = " args='...',"
        else:
            if args_arg:
                args_str = f" args={re.escape(str(args_arg))},"
            else:
                args_str = ""

        kwargs_str = " "
        for key, val in kwargs_arg.items():
            if key in omit_kwargs_arg:
                val = "..."
            if isinstance(val, str):
                kwargs_str += f"{key}='{val}', "
            else:
                kwargs_str += f"{key}={val}, "

        kwargs_str = re.escape(kwargs_str)

        exp_entry_log_msg = (
            rf"{file_name}{target_qual_name}:{target_line_num} entry:{args_str}"
            f"{kwargs_str}"
            f"caller: {file_name}::{caller_qual_name}:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        if omit_ret_val_arg:
            ret_value = "return value omitted"
        elif ret_kw2:
            ret_value = "return_value=2.2"
        else:
            ret_value = "return_value=None"

        exp_exit_log_msg = (
            f"{file_name}{target_qual_name}:{target_line_num} exit: {ret_value}"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_etrace_combo_omits
    ####################################################################
    p_args_to_use = map(lambda n: dict(p_args_list[0:n]), range(len(p_args_list) + 1))
    kwargs_to_use = map(lambda n: dict(kwargs_list[0:n]), range(len(kwargs_list) + 1))

    p_args_and_omits = it.chain.from_iterable(
        map(
            lambda kwdict: it.product([kwdict], mi.powerset(kwdict.keys())),
            p_args_to_use,
        )
    )

    kwargs_and_omits = it.chain.from_iterable(
        map(
            lambda kwdict: it.product([kwdict], mi.powerset(kwdict.keys())),
            kwargs_to_use,
        )
    )

    @pytest.mark.parametrize("caller_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("target_type_arg", FunctionTypeList)
    @pytest.mark.parametrize("p_args_and_omits_arg", p_args_and_omits)
    @pytest.mark.parametrize("kwargs_and_omits_arg", kwargs_and_omits)
    @pytest.mark.parametrize("omit_ret_val_arg", (True, False))
    def test_etrace_combo_omits2(
        self,
        caller_type_arg: FunctionType,
        target_type_arg: FunctionType,
        p_args_and_omits_arg: tuple[dict[str, Any], tuple[str]],
        kwargs_and_omits_arg: tuple[dict[str, Any], tuple[str]],
        omit_ret_val_arg: bool,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test etrace on a function.

        caller_type_arg: type of function that makes the call
        target_type_arg: type of function to be called
        p_args_and_omits_arg: positional args and list of omits
        kwargs_and_omits_arg: dict and list of omits
        omit_ret_val_arg: if True, omit ret value fro exit trace
        caplog: pytest fixture to capture log output

        """
        if target_type_arg == FunctionType.InitMethod:
            trace_enabled = True
        else:
            trace_enabled = False

        p_args_dict: dict[str, Any] = p_args_and_omits_arg[0]
        p_args_arg = p_args_dict.values()
        omit_p_args_arg: list[str] = list(p_args_and_omits_arg[1])

        kwargs_arg: dict[str, Any] = kwargs_and_omits_arg[0]
        omit_kwargs_arg: list[str] = list(kwargs_and_omits_arg[1])

        omit_parms_list: list[str] = omit_p_args_arg.copy() + omit_kwargs_arg.copy()

        class CallTarget(Protocol):
            def __call__(  # noqa E704
                self,
                a1: Optional[str] = None,
                a2: Optional[int] = None,
                a3: Optional[str] = None,
                a4: Optional[list[Any]] = None,
                *,
                kw1: int = 111,
                kw2: float = 22.22,
                kw3: str = "threes_company",
                kw4: Optional[list[Any]] = None,
            ) -> Any: ...

        @etrace(
            omit_parms=omit_parms_list,
            omit_return_value=omit_ret_val_arg,
        )
        def f1(
            a1: Optional[str] = None,
            a2: Optional[int] = None,
            a3: Optional[str] = None,
            a4: Optional[list[Any]] = None,
            *,
            kw1: int = 111,
            kw2: float = 22.22,
            kw3: str = "threes_company",
            kw4: Optional[list[Any]] = None,
        ) -> list[str | int | list[Any] | float | None]:
            return [a1, a2, a3, a4, kw1, kw2, kw3, kw4]

        class Caller:
            def __init__(self) -> None:
                if caller_type_arg == FunctionType.InitMethod:
                    target_rtn(*p_args_arg, **kwargs_arg)

            def caller(self) -> None:
                target_rtn(*p_args_arg, **kwargs_arg)

            @staticmethod
            def static_caller() -> None:
                target_rtn(*p_args_arg, **kwargs_arg)

            @classmethod
            def class_caller(cls) -> None:
                target_rtn(*p_args_arg, **kwargs_arg)

        class Target:
            @etrace(
                enable_trace=trace_enabled,
                omit_parms=omit_parms_list,
                omit_return_value=omit_ret_val_arg,
            )
            def __init__(
                self,
                a1: Optional[str] = None,
                a2: Optional[int] = None,
                a3: Optional[str] = None,
                a4: Optional[list[Any]] = None,
                *,
                kw1: int = 111,
                kw2: float = 22.22,
                kw3: str = "threes_company",
                kw4: Optional[list[Any]] = None,
            ) -> None:
                self.a1 = a1
                self.a2 = a2
                self.a3 = a3
                self.a4 = a4
                self.kw1 = kw1
                self.kw2 = kw2
                self.kw3 = kw3
                self.kw4 = kw4

            @etrace(
                omit_parms=omit_parms_list,
                omit_return_value=omit_ret_val_arg,
            )
            def target(
                self,
                a1: Optional[str] = None,
                a2: Optional[int] = None,
                a3: Optional[str] = None,
                a4: Optional[list[Any]] = None,
                *,
                kw1: int = 111,
                kw2: float = 22.22,
                kw3: str = "threes_company",
                kw4: Optional[list[Any]] = None,
            ) -> list[str | int | list[Any] | float | None]:
                return [a1, a2, a3, a4, kw1, kw2, kw3, kw4]

            @etrace(
                omit_parms=omit_parms_list,
                omit_return_value=omit_ret_val_arg,
            )
            @staticmethod
            def static_target(
                a1: Optional[str] = None,
                a2: Optional[int] = None,
                a3: Optional[str] = None,
                a4: Optional[list[Any]] = None,
                *,
                kw1: int = 111,
                kw2: float = 22.22,
                kw3: str = "threes_company",
                kw4: Optional[list[Any]] = None,
            ) -> list[str | int | list[Any] | float | None]:
                return [a1, a2, a3, a4, kw1, kw2, kw3, kw4]

            @etrace(
                omit_parms=omit_parms_list,
                omit_return_value=omit_ret_val_arg,
            )
            @classmethod
            def class_target(
                cls,
                a1: Optional[str] = None,
                a2: Optional[int] = None,
                a3: Optional[str] = None,
                a4: Optional[list[Any]] = None,
                *,
                kw1: int = 111,
                kw2: float = 22.22,
                kw3: str = "threes_company",
                kw4: Optional[list[Any]] = None,
            ) -> list[str | int | list[Any] | float | None]:
                return [a1, a2, a3, a4, kw1, kw2, kw3, kw4]

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_utils.entry_trace")

        file_name = "test_entry_trace.py"

        ################################################################
        # choose the target function or method
        ################################################################
        target_rtn: CallTarget | Callable[[str | int | list[Any] | float | None], Any]
        if target_type_arg == FunctionType.Function:
            target_rtn = f1
            target_line_num = inspect.getsourcelines(f1)[1]
            target_qual_name = "::f1"

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

        log_args = {
            "a1": None,
            "a2": None,
            "a3": None,
            "a4": None,
            "kw1": 111,
            "kw2": 22.22,
            "kw3": "threes_company",
            "kw4": None,
        }

        log_return = {
            "a1": None,
            "a2": None,
            "a3": None,
            "a4": None,
            "kw1": 111,
            "kw2": 22.22,
            "kw3": "threes_company",
            "kw4": None,
        }

        for key, val in p_args_dict.items():
            log_return[key] = val
            if key in omit_p_args_arg:
                val = "..."
            log_args[key] = val

        for key, val in kwargs_arg.items():
            log_return[key] = val
            if key in omit_kwargs_arg:
                val = "..."
            log_args[key] = val

        args_str = ""
        for key, val in log_args.items():
            if isinstance(val, str):
                args_str += f"{key}='{val}', "
            else:
                args_str += f"{key}={val}, "

        args_str = re.escape(args_str)

        ################################################################
        # call the function or method
        ################################################################
        if caller_type_arg == FunctionType.Function:
            target_rtn(*p_args_arg, **kwargs_arg)
            caller_qual_name = "TestEntryTraceCombos.test_etrace_combo_omits2"

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

        if omit_ret_val_arg:
            ret_value = "return value omitted"
        elif target_type_arg == FunctionType.InitMethod:
            ret_value = "return_value=None"
        else:
            ret_value = re.escape(f"return_value={list(log_return.values())}")

        exp_entry_log_msg = (
            rf"{file_name}{target_qual_name}:{target_line_num} entry: {args_str}"
            f"caller: {file_name}::{caller_qual_name}:[0-9]+"
        )

        log_ver.add_pattern(pattern=exp_entry_log_msg)

        exp_exit_log_msg = (
            f"{file_name}{target_qual_name}:{target_line_num} exit: {ret_value}"
        )

        log_ver.add_pattern(pattern=exp_exit_log_msg)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)
