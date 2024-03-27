"""test_log_verifier.py module."""

########################################################################
# Standard Library
########################################################################
from collections.abc import Iterable
from dataclasses import dataclass, field
import itertools as it
import more_itertools as mi
import logging
import numpy as np
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


class LogFailedVerification(ErrorTstLogVer):
    """Verification of log failed"""

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


@dataclass
class LogItemDescriptor:
    log_name: str
    log_level: int
    item: str
    match_array: np.ndarray  # np.ndarray([0])
    c_pattern: re.Pattern[str] = ""
    fullmatch: bool = False


@dataclass
class LogSectionLineItem:
    log_name: str
    log_level: int
    item: str
    fullmatch: str
    num_items: int
    num_actual_unmatches: int
    num_actual_matches: int
    num_counted_unmatched: int = 0
    num_counted_matched: int = 0


@dataclass
class LogSection:
    hdr_line: str
    start_idx: int
    end_idx: int
    line_items: dict[str, LogSectionLineItem] = field(default_factory=dict)


@dataclass
class LogVerScenario:
    num_matched_patterns: int = 0
    num_matched_log_msgs: int = 0
    num_unmatched_items: int = 0
    unmatched_patterns: list[LogItemDescriptor] = field(default_factory=list)
    matched_patterns: list[LogItemDescriptor] = field(default_factory=list)
    unmatched_log_msgs: list[LogItemDescriptor] = field(default_factory=list)
    matched_log_msgs: list[LogItemDescriptor] = field(default_factory=list)


@dataclass
class ItemStats:
    num_items: int = 0
    num_matched_items: int = 0
    num_unmatched_items: int = 0


class TestLogVerification:
    """Verify the log output."""

    def __init__(
        self,
        log_name: str,
        capsys_to_use: pytest.CaptureFixture[str],
        caplog_to_use: pytest.LogCaptureFixture,
    ):
        self.log_name: str = log_name
        self.capsys_to_use = capsys_to_use
        self.caplog_to_use = caplog_to_use
        self.loggers: dict[str, logging.Logger] = {}
        self.patterns: list[LogItemDescriptor] = []
        self.log_msgs: list[LogItemDescriptor] = []

        self.matches_array: list[np.ndarray] = []

        self.loggers[log_name] = logging.getLogger(log_name)

        self.log_ver = LogVer(log_name=log_name)

        self.stats: dict[str, ItemStats] = {}
        self.scenarios: list[LogVerScenario] = []

        self.capsys_stats_hdr: str = ""
        self.capsys_stats_lines: list[str] = []
        self.capsys_sections: dict[str, LogSection] = {}

        self.captured_pattern_stats_line: str = ""
        self.captured_log_msgs_stats_line: str = ""
        self.captured_num_matches: int = 0

    def add_scenario(self, scenario: LogVerScenario):
        pass

    def issue_log_msg(
        self,
        log_msg: str,
        log_level: int = logging.DEBUG,
        log_name: Optional[str] = None,
    ):
        if log_name is None:
            log_name = self.log_name
        self.loggers[log_name].log(log_level, log_msg)
        self.log_msgs.append(
            LogItemDescriptor(
                log_name=log_name,
                log_level=log_level,
                item=log_msg,
                match_array=np.zeros(1),
            )
        )

    def add_pattern(
        self,
        pattern: str,
        log_level: int = logging.DEBUG,
        log_name: Optional[str] = None,
        fullmatch: bool = False,
    ):
        if log_name is None:
            log_name = self.log_name
        self.log_ver.add_pattern(
            pattern=pattern, log_level=log_level, log_name=log_name, fullmatch=fullmatch
        )
        self.patterns.append(
            LogItemDescriptor(
                log_name=log_name,
                log_level=log_level,
                item=pattern,
                match_array=np.zeros(1),
                c_pattern=re.compile(pattern),
                fullmatch=fullmatch,
            )
        )

    def verify_results(
        self,
        exp_num_unmatched_patterns: Optional[int] = None,
        exp_num_unmatched_log_msgs: Optional[int] = None,
        exp_num_matched_log_msgs: Optional[int] = None,
    ) -> None:
        """Verify the log records."""
        self.build_ver_record()

        if exp_num_unmatched_patterns is not None:
            assert (
                self.stats["patterns"].num_unmatched_items == exp_num_unmatched_patterns
            )
        if exp_num_unmatched_log_msgs is not None:
            assert (
                self.stats["log_msgs"].num_unmatched_items == exp_num_unmatched_log_msgs
            )
        if exp_num_matched_log_msgs is not None:
            assert self.stats["log_msgs"].num_matched_items == exp_num_matched_log_msgs

        patterns_stats_line = (
            f" patterns "
            f"{self.stats['patterns'].num_items:>10} "
            f"{self.stats['patterns'].num_matched_items:>12} "
            f"{self.stats['patterns'].num_unmatched_items:>14}"
        )

        log_msgs_stats_line = (
            f" log_msgs "
            f"{self.stats['log_msgs'].num_items:>10} "
            f"{self.stats['log_msgs'].num_matched_items:>12} "
            f"{self.stats['log_msgs'].num_unmatched_items:>14}"
        )

        assert self.captured_pattern_stats_line == patterns_stats_line
        assert self.captured_log_msgs_stats_line == log_msgs_stats_line

        @dataclass
        class VerResult:
            unmatched_patterns: bool = False
            unmatched_log_msgs: bool = False
            matched_log_msgs: bool = False

        ver_result_array: dict[int, VerResult] = {}
        for idx, scenario in enumerate(self.scenarios):
            ver_result = VerResult()
            if self.verify_lines(
                item_text="pattern",
                num_unmatched_stats=self.stats["patterns"].num_unmatched_items,
                num_matched_stats=self.stats["patterns"].num_matched_items,
                unmatched_items=scenario.unmatched_patterns,
                matched_items=scenario.matched_patterns,
                log_section=self.capsys_sections["unmatched_patterns"],
                matched_section=False,
            ):
                ver_result.unmatched_patterns = True

            if self.verify_lines(
                item_text="log_msg",
                num_unmatched_stats=self.stats["log_msgs"].num_unmatched_items,
                num_matched_stats=self.stats["log_msgs"].num_matched_items,
                unmatched_items=scenario.unmatched_log_msgs,
                matched_items=scenario.matched_log_msgs,
                log_section=self.capsys_sections["unmatched_log_msgs"],
                matched_section=False,
            ):
                ver_result.unmatched_log_msgs = True

            if self.verify_lines(
                item_text="log_msg",
                num_unmatched_stats=self.stats["log_msgs"].num_unmatched_items,
                num_matched_stats=self.stats["log_msgs"].num_matched_items,
                unmatched_items=scenario.unmatched_log_msgs,
                matched_items=scenario.matched_log_msgs,
                log_section=self.capsys_sections["matched_log_msgs"],
                matched_section=True,
            ):
                ver_result.matched_log_msgs = True

            if (
                ver_result.unmatched_patterns
                and ver_result.unmatched_log_msgs
                and ver_result.matched_log_msgs
            ):
                return
            ver_result_array[idx] = ver_result

        raise LogFailedVerification(f"log failed to verify \n{ver_result_array=}")

    def verify_lines(
        self,
        item_text: str,
        num_unmatched_stats: int,
        num_matched_stats: int,
        unmatched_items: list[LogItemDescriptor],
        matched_items: list[LogItemDescriptor],
        log_section: LogSection,
        matched_section: bool,
    ) -> bool:
        # logger.debug(
        #     f"verify_lines entry: {item_text=}, {num_unmatched_stats=}, {num_matched_stats=}, "
        #     f"{unmatched_items=}, {matched_items=}, {log_section=}, {matched_section=}"
        # )
        exp_records = True
        if matched_section:
            exp_records = False
            if num_matched_stats == 0:
                assert len(matched_items) == 0
                assert len(log_section.line_items) == 0
                # logger.debug(f"verify_lines returning True 1")
                return True
            else:
                for matched_item in matched_items:
                    unmatched_found = False
                    for unmatched_item in unmatched_items:
                        if (
                            matched_item.item == unmatched_item.item
                            and matched_item.log_name == unmatched_item.log_name
                            and matched_item.log_level == unmatched_item.log_level
                        ):
                            unmatched_found = True
                            break
                    if not unmatched_found:
                        exp_records = True
                        break
        else:
            if num_unmatched_stats == 0:
                assert len(unmatched_items) == 0
                assert len(log_section.line_items) == 0
                # logger.debug(f"verify_lines returning True 2")
                return True
            else:
                assert len(unmatched_items) > 0
                assert len(log_section.line_items) > 0

        max_log_name_len = 0
        max_log_msg_len = 0
        for item in unmatched_items:
            max_log_name_len = max(max_log_name_len, len(item.log_name))
            max_log_msg_len = max(max_log_msg_len, len(item.item))
        for item in matched_items:
            max_log_name_len = max(max_log_name_len, len(item.log_name))
            max_log_msg_len = max(max_log_msg_len, len(item.item))

        if exp_records:
            if item_text == "pattern":
                fullmatch_text = "  fullmatch"
            else:
                fullmatch_text = ""

            expected_hdr_line = (
                " " * (max_log_name_len - len("log_name"))
                + "log_name"
                + " "
                + " log_level"
                + " "
                + " " * (max_log_msg_len - len(item_text))
                + item_text
                + fullmatch_text
                + "  num_records"
                + "  num_matched"
            )
            if log_section.hdr_line != expected_hdr_line:
                # logger.debug(
                #     f"verify_lines returning False 3 "
                #     f"\n{log_section.hdr_line=} \n{expected_hdr_line=}"
                # )
                return False

            for key in log_section.line_items.keys():
                log_section.line_items[key].num_counted_unmatched = 0
                log_section.line_items[key].num_counted_matched = 0

            for item in unmatched_items:
                if item_text == "pattern":
                    key = f"{item.item}{item.fullmatch}"
                else:
                    key = item.item

                if key in log_section.line_items:
                    log_section.line_items[key].num_counted_unmatched += 1

            for item in matched_items:
                if item_text == "pattern":
                    key = f"{item.item}{item.fullmatch}"
                else:
                    key = item.item
                if key in log_section.line_items:
                    log_section.line_items[key].num_counted_matched += 1

            for key, line_item in log_section.line_items.items():
                if line_item.num_actual_matches != line_item.num_counted_matched:
                    # logger.debug(
                    #     f"verify_lines returning False 4 "
                    #     f"{line_item.num_actual_matches=} {line_item.num_counted_matched=}"
                    # )
                    return False
                if line_item.num_actual_unmatches != line_item.num_counted_unmatched:
                    # logger.debug(
                    #     f"verify_lines returning False 5 "
                    #     f"{line_item.num_actual_unmatches=} {line_item.num_counted_unmatched=}"
                    # )
                    return False

        # logger.debug(f"verify_lines returning True 6")
        return True

    def build_ver_record(self):
        # self.build_scenarios()
        self.get_ver_output_lines()
        self.build_scenarios()

    def get_ver_output_lines(self):

        stats_asterisks = "************************************************"
        stats_line = "*                summary stats                 *"

        unmatched_patterns_hdr_line = "* unmatched patterns: *"
        unmatched_log_msgs_hdr_line = "* unmatched log_msgs: *"
        matched_log_msgs_hdr_line = "*  matched log_msgs:  *"

        # patterns_stats_line = (
        #     f" patterns "
        #     f"{self.stats['patterns'].num_items:>10} "
        #     f"{self.stats['patterns'].num_matched_items:>12} "
        #     f"{self.stats['patterns'].num_unmatched_items:>14}"
        # )
        #
        # log_msgs_stats_line = (
        #     f" log_msgs "
        #     f"{self.stats['log_msgs'].num_items:>10} "
        #     f"{self.stats['log_msgs'].num_matched_items:>12} "
        #     f"{self.stats['log_msgs'].num_unmatched_items:>14}"
        # )
        # clear the capsys
        captured = self.capsys_to_use.readouterr().out

        # get log results and print them
        log_results = self.log_ver.get_match_results(self.caplog_to_use)
        self.log_ver.print_match_results(log_results)

        captured = self.capsys_to_use.readouterr().out
        captured_lines = captured.split("\n")

        assert captured_lines[0] == ""
        assert captured_lines[1] == stats_asterisks
        assert captured_lines[2] == stats_line
        assert captured_lines[3] == stats_asterisks
        assert captured_lines[4] == "item_type  num_items  num_matched  num_unmatched"
        # assert captured_lines[5] == patterns_stats_line
        # assert captured_lines[6] == log_msgs_stats_line
        assert captured_lines[7] == ""

        self.captured_pattern_stats_line = captured_lines[5]
        self.captured_log_msgs_stats_line = captured_lines[6]
        split_log_msgs_stats = self.captured_log_msgs_stats_line.split()
        self.captured_num_matches = int(split_log_msgs_stats[2])

        section_item = self.get_section(
            start_idx=8,
            captured_lines=captured_lines,
            section_hdr_line=unmatched_patterns_hdr_line,
            section_is_pattern=True,
        )

        self.capsys_sections["unmatched_patterns"] = section_item

        section_item = self.get_section(
            start_idx=section_item.end_idx + 1,
            captured_lines=captured_lines,
            section_hdr_line=unmatched_log_msgs_hdr_line,
            section_is_pattern=False,
        )

        self.capsys_sections["unmatched_log_msgs"] = section_item

        section_item = self.get_section(
            start_idx=section_item.end_idx + 1,
            captured_lines=captured_lines,
            section_hdr_line=matched_log_msgs_hdr_line,
            section_is_pattern=False,
        )

        self.capsys_sections["matched_log_msgs"] = section_item

    def get_section(
        self,
        start_idx: int,
        captured_lines: list[str],
        section_hdr_line: str,
        section_is_pattern: bool,
    ) -> LogSection:
        section_asterisks = "***********************"
        assert captured_lines[start_idx] == section_asterisks
        assert captured_lines[start_idx + 1] == section_hdr_line
        assert captured_lines[start_idx + 2] == section_asterisks
        if captured_lines[start_idx + 3] == "":
            return LogSection(
                hdr_line="",
                start_idx=start_idx,
                end_idx=start_idx + 3,
                line_items={},
            )

        ret_section = LogSection(
            hdr_line=captured_lines[start_idx + 3],
            start_idx=start_idx,
            end_idx=0,
            line_items={},
        )

        for idx in range(start_idx + 4, len(captured_lines)):
            if captured_lines[idx] == "":
                ret_section.end_idx = idx
                return ret_section
            else:
                if section_is_pattern:
                    rsplit_actual = captured_lines[idx].rsplit(maxsplit=3)
                    fm_text = rsplit_actual[1]
                else:
                    rsplit_actual = captured_lines[idx].rsplit(maxsplit=2)
                    fm_text = ""

                lsplit_actual = rsplit_actual[0].split(maxsplit=2)

                log_name = lsplit_actual[0]
                log_level = int(lsplit_actual[1])

                item = lsplit_actual[2]

                key = item + fm_text

                num_items = int(rsplit_actual[-2])
                num_matches = int(rsplit_actual[-1])

                ret_section.line_items[key] = LogSectionLineItem(
                    log_name=log_name,
                    log_level=log_level,
                    item=item,
                    fullmatch=fm_text,
                    num_items=num_items,
                    num_actual_unmatches=num_items - num_matches,
                    num_actual_matches=num_matches,
                    num_counted_unmatched=0,
                    num_counted_matched=0,
                )

    def build_scenarios(self) -> None:

        patterns_len = len(self.patterns)
        log_msgs_len = len(self.log_msgs)

        if patterns_len == 0 or log_msgs_len == 0:
            self.stats["patterns"] = ItemStats(
                num_items=patterns_len,
                num_matched_items=0,
                num_unmatched_items=patterns_len,
            )
            self.stats["log_msgs"] = ItemStats(
                num_items=log_msgs_len,
                num_matched_items=0,
                num_unmatched_items=log_msgs_len,
            )
            self.scenarios.append(
                LogVerScenario(
                    unmatched_patterns=self.patterns, unmatched_log_msgs=self.log_msgs
                )
            )
            return

        def build_scenario(
            pattern_desc: LogItemDescriptor, log_msg_desc: LogItemDescriptor
        ):
            nonlocal staging_scenario
            if (
                (
                    (
                        pattern_desc.fullmatch
                        and pattern_desc.c_pattern.fullmatch(log_msg_desc.item)
                    )
                    or (
                        not pattern_desc.fullmatch
                        and pattern_desc.c_pattern.match(log_msg_desc.item)
                    )
                )
                and pattern_desc.log_name == log_msg_desc.log_name
                and pattern_desc.log_level == log_msg_desc.log_level
            ):
                staging_scenario.num_matched_patterns += 1
                staging_scenario.matched_patterns.append(pattern_desc)
                staging_scenario.num_matched_log_msgs += 1
                staging_scenario.matched_log_msgs.append(log_msg_desc)
            else:
                staging_scenario.num_unmatched_items += 1
                staging_scenario.unmatched_patterns.append(pattern_desc)
                staging_scenario.unmatched_log_msgs.append(log_msg_desc)

        completed_scenarios: list[LogVerScenario] = []
        max_matched_msgs = 0
        ################################################################
        # pre-build the matched arrays
        ################################################################
        self.build_match_arrays(patterns_len=patterns_len, log_msgs_len=log_msgs_len)
        if patterns_len < log_msgs_len:
            log_msg_perms = list(it.permutations(self.log_msgs))
            match_perms = it.permutations(self.matches_array)
            for idx, match_perm in enumerate(match_perms):
                diag_match_array = np.ndarray(match_perm)
                num_matched_items = np.trace(diag_match_array)
                max_matched_msgs = max(max_matched_msgs, num_matched_items)

                if num_matched_items == self.captured_num_matches:
                    staging_scenario: LogVerScenario = LogVerScenario(
                        num_matched_patterns=num_matched_items,
                        num_matched_log_msgs=num_matched_items,
                    )
                    log_msg_perm = log_msg_perms[idx]
                    for idx2 in range(patterns_len):
                        if diag_match_array[idx2, idx2]:
                            staging_scenario.matched_patterns.append(
                                self.patterns[idx2]
                            )
                            staging_scenario.matched_log_msgs.append(log_msg_perm[idx2])
                        else:
                            staging_scenario.unmatched_patterns.append(
                                self.patterns[idx2]
                            )
                            staging_scenario.unmatched_log_msgs.append(
                                log_msg_perm[idx2]
                            )
                    staging_scenario.unmatched_log_msgs.extend(
                        log_msg_perm[patterns_len:]
                    )
                    self.scenarios.append(staging_scenario)
                else:
                    assert num_matched_items <= self.captured_num_matches

        else:
            pattern_perms = list(it.permutations(self.patterns))
            match_perms = it.permutations(self.matches_array)
            for idx, match_perm in enumerate(match_perms):
                diag_match_array = np.ndarray(match_perm)
                num_matched_items = np.trace(diag_match_array)
                max_matched_msgs = max(max_matched_msgs, num_matched_items)

                if num_matched_items == self.captured_num_matches:
                    staging_scenario: LogVerScenario = LogVerScenario(
                        num_matched_patterns=num_matched_items,
                        num_matched_log_msgs=num_matched_items,
                    )
                    pattern_perm = pattern_perms[idx]
                    for idx2 in range(log_msgs_len):
                        if diag_match_array[idx2, idx2]:
                            staging_scenario.matched_patterns.append(pattern_perm[idx2])
                            staging_scenario.matched_log_msgs.append(
                                self.log_msgs[idx2]
                            )
                        else:
                            staging_scenario.unmatched_patterns.append(
                                pattern_perm[idx2]
                            )
                            staging_scenario.unmatched_log_msgs.append(
                                self.log_msgs[idx2]
                            )
                    staging_scenario.unmatched_patterns.extend(
                        pattern_perm[log_msgs_len:]
                    )
                    self.scenarios.append(staging_scenario)
                else:
                    assert num_matched_items <= self.captured_num_matches
        # if patterns_len < log_msgs_len:
        #     log_msg_perms = it.permutations(self.log_msgs)
        #     num_unmatched_allowed = patterns_len - self.captured_num_matches
        #     for log_msg_perm in log_msg_perms:
        #         continue_flag = False
        #         staging_scenario: LogVerScenario = LogVerScenario()
        #         # mi.consume(map(build_scenario, self.patterns, log_msg_perm))
        #         for idx in range(patterns_len):
        #             build_scenario(self.patterns[idx], log_msg_perm[idx])
        #             if staging_scenario.num_unmatched_items > num_unmatched_allowed:
        #                 continue_flag = True
        #                 break
        #
        #         if continue_flag:
        #             continue
        #         # if staging_scenario.num_matched_log_msgs < max_matched_msgs:
        #         #     continue
        #         max_matched_msgs = max(
        #             max_matched_msgs, staging_scenario.num_matched_log_msgs
        #         )
        #         staging_scenario.unmatched_log_msgs.extend(log_msg_perm[patterns_len:])
        #         completed_scenarios.append(staging_scenario)
        # else:
        #     pattern_perms = it.permutations(self.patterns)
        #     num_unmatched_allowed = log_msgs_len - self.captured_num_matches
        #     for pattern_perm in pattern_perms:
        #         continue_flag = False
        #         staging_scenario: LogVerScenario = LogVerScenario()
        #         # mi.consume(map(build_scenario, pattern_perm, self.log_msgs))
        #         for idx in range(log_msgs_len):
        #             build_scenario(pattern_perm[idx], self.log_msgs[idx])
        #             if staging_scenario.num_unmatched_items > num_unmatched_allowed:
        #                 continue_flag = True
        #                 break
        #
        #         if continue_flag:
        #             continue
        #         # if staging_scenario.num_matched_log_msgs < max_matched_msgs:
        #         #     continue
        #         max_matched_msgs = max(
        #             max_matched_msgs, staging_scenario.num_matched_log_msgs
        #         )
        #         staging_scenario.unmatched_patterns.extend(pattern_perm[log_msgs_len:])
        #         completed_scenarios.append(staging_scenario)

        # for scenario in completed_scenarios:
        #     if scenario.num_matched_log_msgs == max_matched_msgs:
        #         self.scenarios.append(scenario)

        # logger.debug(f"{max_matched_msgs=}")
        self.stats["patterns"] = ItemStats(
            num_items=patterns_len,
            num_matched_items=max_matched_msgs,
            num_unmatched_items=patterns_len - max_matched_msgs,
        )
        self.stats["log_msgs"] = ItemStats(
            num_items=log_msgs_len,
            num_matched_items=max_matched_msgs,
            num_unmatched_items=log_msgs_len - max_matched_msgs,
        )

    def build_match_arrays(self, patterns_len: int, log_msgs_len: int) -> None:
        if patterns_len < log_msgs_len:
            for log_msg_desc in self.log_msgs:
                match_array: np.ndarray = np.zeros(log_msgs_len)
                for idx, pattern_desc in enumerate(self.patterns):
                    if (
                        (
                            (
                                pattern_desc.fullmatch
                                and pattern_desc.c_pattern.fullmatch(log_msg_desc.item)
                            )
                            or (
                                not pattern_desc.fullmatch
                                and pattern_desc.c_pattern.match(log_msg_desc.item)
                            )
                        )
                        and pattern_desc.log_name == log_msg_desc.log_name
                        and pattern_desc.log_level == log_msg_desc.log_level
                    ):
                        match_array[idx] = 1
                self.matches_array.append(match_array)

        else:
            for pattern_desc in self.patterns:
                match_array: np.ndarray = np.zeros(patterns_len)
                for idx, log_msg_desc in enumerate(self.log_msgs):
                    if (
                        (
                            (
                                pattern_desc.fullmatch
                                and pattern_desc.c_pattern.fullmatch(log_msg_desc.item)
                            )
                            or (
                                not pattern_desc.fullmatch
                                and pattern_desc.c_pattern.match(log_msg_desc.item)
                            )
                        )
                        and pattern_desc.log_name == log_msg_desc.log_name
                        and pattern_desc.log_level == log_msg_desc.log_level
                    ):
                        match_array[idx] = 1
                self.matches_array.append(match_array)


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
        "msg0",
        "msg1",
        "msg2",
        "msg3",
        "msg[12]{1}",
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

    # @pytest.mark.parametrize("msgs_arg", msg_combos_list)
    # @pytest.mark.parametrize("patterns_arg", pattern_combos_list)
    @pytest.mark.parametrize("msgs_arg", [("msg1", "msg1", "msg2")])
    @pytest.mark.parametrize("patterns_arg", [("msg1", "msg[123]{1}")])
    def test_log_verifier_contention2(
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
        print(f"\n{msgs_arg=}\n{patterns_arg=}")
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
            potential_list = list(potential_msgs & set(filter_msgs))
            sorted_pl = sort_items(potential_list, filter_msgs, sort_x_y_item)
            ret_potential_list = []
            for item in sorted_pl:
                item_count = filter_msgs.count(item)
                ret_potential_list.append([item_count, item])
            return ret_potential_list

        unmatched_patterns: list[str] = []
        unmatched_patterns2: list[str] = []
        matched_patterns: list[str] = []
        matched_patterns2: list[str] = []

        unmatched_msgs: list[str] = []
        unmatched_msgs2: list[str] = []
        matched_msgs: list[str] = []
        matched_msgs2: list[str] = []

        pattern_df = pd.DataFrame()
        msg_df = pd.DataFrame()

        ################################################################
        # create pandas array for patterns
        ################################################################
        no_match_patterns = []
        if patterns_arg:
            pattern_df = pd.DataFrame(patterns_arg, columns=["item"])

            pattern_df["potential_finds"] = pattern_df["item"].map(matched_msg_array)
            pattern_df["potential_finds"] = pattern_df["potential_finds"].apply(
                filter_potential_msgs,
                filter_msgs=msgs_arg_list,
                sort_x_y_item=sort_x_y_x_msg,
            )
            pattern_df["potential_finds2"] = "none"
            for idx in range(len(pattern_df)):
                pot_finds = pattern_df["potential_finds"][idx]
                pattern_df["potential_finds2"][idx] = pot_finds.copy()

            pattern_df["claimed"] = "none"

            # print(f"\npattern_df: \n{pattern_df}")

            for idx in range(len(pattern_df)):
                if len(pattern_df["potential_finds"].iloc[idx]) == 0:
                    no_match_patterns.append(pattern_df["item"].iloc[idx])

        no_match_msgs = []
        if msgs_arg:
            msg_df = pd.DataFrame(msgs_arg, columns=["item"])
            msg_df["potential_finds"] = msg_df["item"].map(matched_pattern_array)
            msg_df["potential_finds"] = msg_df["potential_finds"].apply(
                filter_potential_msgs,
                filter_msgs=patterns_arg_list,
                sort_x_y_item=sort_x_y_x_pattern,
            )
            msg_df["potential_finds2"] = "none"
            for idx in range(len(msg_df)):
                pot_finds = msg_df["potential_finds"][idx]
                msg_df["potential_finds2"][idx] = pot_finds.copy()

            msg_df["claimed"] = "none"

            for idx in range(len(msg_df)):
                if len(msg_df["potential_finds"].iloc[idx]) == 0:
                    no_match_msgs.append(msg_df["item"].iloc[idx])

            # print(f"\nmsg_df: \n{msg_df}")

        test_matched_found_msgs_list = []
        test_unmatched_found_msgs_list = []
        test_matched_found_patterns_list = []
        test_unmatched_found_patterns_list = []

        def remove_potential_find(target_df: pd.DataFrame, potential_item: str):
            for idx in range(len(target_df)):
                potential_finds = target_df["potential_finds"].iloc[idx]
                for idx2 in range(len(potential_finds)):
                    if potential_finds[idx2][1] == potential_item:
                        potential_finds[idx2][0] -= 1
                        if potential_finds[idx2][0] == 0:
                            potential_finds.pop(idx2)
                        break

        def search_df(
            search_arg_df: pd.DataFrame,
            search_targ_df: pd.DataFrame,
            num_potential_items: int,
        ) -> bool:
            for idx in range(len(search_arg_df)):
                if search_arg_df["claimed"].iloc[idx] == "none":
                    search_arg = search_arg_df["item"].iloc[idx]
                    if (
                        len(search_arg_df["potential_finds"].iloc[idx])
                        == num_potential_items
                    ):
                        for potential_find in search_arg_df["potential_finds"].iloc[
                            idx
                        ]:
                            potential_find_item = potential_find[1]
                            for idx2 in range(len(search_targ_df)):
                                if (
                                    potential_find_item
                                    == search_targ_df["item"].iloc[idx2]
                                    and search_targ_df["claimed"].iloc[idx2] == "none"
                                ):
                                    search_arg_df["claimed"].iloc[
                                        idx
                                    ] = potential_find_item
                                    search_targ_df["claimed"].iloc[idx2] = search_arg
                                    remove_potential_find(
                                        target_df=search_arg_df,
                                        potential_item=potential_find_item,
                                    )
                                    remove_potential_find(
                                        target_df=search_targ_df,
                                        potential_item=search_arg,
                                    )
                                    break
                            if search_arg_df["claimed"].iloc[idx] != "none":
                                return True
                                # if num_potential_items == 1:
                                #     break
                                # else:
                                #     return True

        if patterns_arg and msgs_arg:
            ############################################################
            # handle patterns with 1 potential msg
            ############################################################
            find_items = True
            while find_items:
                find_items = False
                for num_items in range(1, 4):
                    # print(f"************* {num_items=}")
                    # print(f"\npattern_df: \n{pattern_df}")
                    # print(f"\nmsg_df: \n{msg_df}")
                    if search_df(
                        search_arg_df=pattern_df,
                        search_targ_df=msg_df,
                        num_potential_items=num_items,
                    ):
                        find_items = True
                        # print(f"\npattern_df 1a{find_items=}: \n{pattern_df}")
                        # print(f"\nmsg_df 1a {find_items=}: \n{msg_df}")
                        break
                    # print(f"\npattern_df 1b {find_items=}: \n{pattern_df}")
                    # print(f"\nmsg_df 1b {find_items=}: \n{msg_df}")
                    if search_df(
                        search_arg_df=msg_df,
                        search_targ_df=pattern_df,
                        num_potential_items=num_items,
                    ):
                        find_items = True
                        # print(f"\npattern_df 2a {find_items=}: \n{pattern_df}")
                        # print(f"\nmsg_df 2a {find_items=}: \n{msg_df}")
                        break
                    # print(f"\npattern_df 2b {find_items=}: \n{pattern_df}")
                    # print(f"\nmsg_df 2b {find_items=}: \n{msg_df}")

            def find_combo_matches(
                item_df: pd.DataFrame,
                items_arg_list: list[str],
                test_matched_found_items_list: list[list[str]],
                test_unmatched_found_items_list: list[list[str]],
                sort_x_y_x_item: str,
            ):
                for perm_idx in it.permutations(range(len(item_df))):
                    item_combo_lists = []
                    for idx in perm_idx:
                        if len(item_df["potential_finds2"].iloc[idx]) > 0:
                            c_items = []
                            for potential_find_item in item_df["potential_finds2"].iloc[
                                idx
                            ]:
                                c_items.append(potential_find_item[1])
                            item_combo_lists.append(c_items)
                        else:
                            item_combo_lists.append(["none"])
                    item_prods = ""
                    if len(item_combo_lists) == 1:
                        item_prods = it.product(
                            item_combo_lists[0],
                        )
                    elif len(item_combo_lists) == 2:
                        item_prods = it.product(
                            item_combo_lists[0],
                            item_combo_lists[1],
                        )
                    elif len(item_combo_lists) == 3:
                        item_prods = it.product(
                            item_combo_lists[0],
                            item_combo_lists[1],
                            item_combo_lists[2],
                        )
                    item_prods = list(item_prods)
                    for item_prod in item_prods:
                        test_found_items = []
                        items_arg_copy = items_arg_list.copy()
                        for item in item_prod:
                            if item in items_arg_copy:
                                test_found_items.append(item)
                                items_arg_copy.remove(item)
                        # test_found_items.sort(key=items_arg.index)
                        test_found_items = sort_items(
                            test_found_items,
                            items_arg_list,
                            sort_x_y_x_item,
                        )
                        items_arg_copy = sort_items(
                            items_arg_copy,
                            items_arg_list,
                            sort_x_y_x_item,
                        )
                        test_matched_found_items_list.append(test_found_items)
                        test_unmatched_found_items_list.append(items_arg_copy.copy())

            find_combo_matches(
                item_df=pattern_df,
                items_arg_list=msgs_arg_list,
                test_matched_found_items_list=test_matched_found_msgs_list,
                test_unmatched_found_items_list=test_unmatched_found_msgs_list,
                sort_x_y_x_item=sort_x_y_x_msg,
            )

            find_combo_matches(
                item_df=msg_df,
                items_arg_list=patterns_arg_list,
                test_matched_found_items_list=test_matched_found_patterns_list,
                test_unmatched_found_items_list=test_unmatched_found_patterns_list,
                sort_x_y_x_item=sort_x_y_x_pattern,
            )

        for idx in range(len(pattern_df)):
            pattern = pattern_df["item"].iloc[idx]
            if pattern_df["claimed"].iloc[idx] == "none":
                unmatched_patterns.append(pattern)
                unmatched_patterns2.append(pattern)
            else:
                matched_patterns.append(pattern)
                matched_patterns2.append(pattern)

        for idx in range(len(msg_df)):
            msg = msg_df["item"].iloc[idx]
            if msg_df["claimed"].iloc[idx] == "none":
                unmatched_msgs.append(msg)
                unmatched_msgs2.append(msg)
            else:
                matched_msgs.append(msg)
                matched_msgs2.append(msg)

        unmatched_msgs = sort_items(unmatched_msgs, msgs_arg_list, sort_x_y_x_msg)
        matched_msgs = sort_items(matched_msgs, msgs_arg_list, sort_x_y_x_msg)

        unmatched_patterns = sort_items(
            unmatched_patterns, patterns_arg_list, sort_x_y_x_pattern
        )
        matched_patterns = sort_items(
            matched_patterns, patterns_arg_list, sort_x_y_x_pattern
        )

        # print(f"\npattern_df: \n{pattern_df}")
        # print(f"\nmsg_df: \n{msg_df}")
        # print(f"{matched_patterns=}")
        # print(f"{unmatched_patterns=}")
        # print(f"{matched_msgs=}")
        # print(f"{unmatched_msgs=}")

        def compare_combos(
            test_matched_found_items_list: list[list[str]],
            test_unmatched_found_items_list: list[list[str]],
            matched_items: list[str],
            unmatched_items: list[str],
            items_arg_list: list[str],
        ):
            num_matched_items_agreed = 0
            num_matched_items_not_agreed = 0
            num_unmatched_items_agreed = 0
            num_unmatched_items_not_agreed = 0
            if patterns_arg_list and msgs_arg_list:
                for test_unmatched_found_items in test_unmatched_found_items_list:
                    if test_unmatched_found_items == unmatched_items:
                        num_unmatched_items_agreed += 1
                    else:
                        num_unmatched_items_not_agreed += 1

                for test_matched_found_items in test_matched_found_items_list:
                    if test_matched_found_items == matched_items:
                        num_matched_items_agreed += 1
                    else:
                        num_matched_items_not_agreed += 1
                        # print(
                        #     f"{len(test_matched_found_items)=},"
                        #     f" {test_matched_found_items=}"
                        #     f"{len(matched_items)=}, {matched_items=}"
                        # )
                        assert len(test_matched_found_items) <= len(matched_items)
            else:
                if not matched_items and unmatched_items == items_arg_list:
                    num_matched_items_agreed = 1
                    num_matched_items_not_agreed = 0
                    num_unmatched_items_agreed = 1
                    num_unmatched_items_not_agreed = 0

            return (
                num_matched_items_agreed,
                num_matched_items_not_agreed,
                num_unmatched_items_agreed,
                num_unmatched_items_not_agreed,
            )

        (
            num_matched_msgs_agreed,
            num_matched_msgs_not_agreed,
            num_unmatched_msgs_agreed,
            num_unmatched_msgs_not_agreed,
        ) = compare_combos(
            test_matched_found_items_list=test_matched_found_msgs_list,
            test_unmatched_found_items_list=test_unmatched_found_msgs_list,
            matched_items=matched_msgs,
            unmatched_items=unmatched_msgs,
            items_arg_list=msgs_arg_list,
        )

        (
            num_matched_patterns_agreed,
            num_matched_patterns_not_agreed,
            num_unmatched_patterns_agreed,
            num_unmatched_patterns_not_agreed,
        ) = compare_combos(
            test_matched_found_items_list=test_matched_found_patterns_list,
            test_unmatched_found_items_list=test_unmatched_found_patterns_list,
            matched_items=matched_patterns,
            unmatched_items=unmatched_patterns,
            items_arg_list=patterns_arg_list,
        )

        #
        # print(f"{num_unmatched_msgs_agreed=}")
        # print(f"{num_unmatched_msgs_not_agreed=}")
        #
        # print(f"{num_matched_msgs_agreed=}")
        # print(f"{num_matched_msgs_not_agreed=}")
        #
        # print(f"{num_unmatched_patterns_agreed=}")
        # print(f"{num_unmatched_patterns_not_agreed=}")
        #
        # print(f"{num_matched_patterns_agreed=}")
        # print(f"{num_matched_patterns_not_agreed=}")

        assert num_unmatched_msgs_agreed
        assert num_matched_msgs_agreed

        assert num_unmatched_patterns_agreed
        assert num_matched_patterns_agreed

        ################################################################
        # add patterns and issue log msgs
        ################################################################
        caplog.clear()

        log_name = "contention_0"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        fullmatch_tf_arg = True
        for pattern in patterns_arg:
            log_ver.add_msg(log_msg=pattern, fullmatch=fullmatch_tf_arg)

        for msg in msgs_arg:
            t_logger.debug(msg)

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))

        # print(f"{unmatched_patterns=}")
        # print(f"{unmatched_msgs=}")
        # print(f"{matched_msgs=}")

        # if unmatched_patterns:
        #     with pytest.raises(UnmatchedExpectedMessages):
        #         log_ver.verify_log_results(log_results)
        # elif unmatched_msgs:
        #     with pytest.raises(UnmatchedActualMessages):
        #         log_ver.verify_log_results(log_results)
        # else:
        #     log_ver.verify_log_results(log_results)

        expected_result = "\n"
        expected_result += f"{msgs_arg=}\n"
        expected_result += f"{patterns_arg=}\n"

        expected_result += "\n"
        expected_result += "**********************************\n"
        expected_result += f"* number expected log records: {len(patterns_arg)} *\n"
        expected_result += (
            f"* number expected unmatched  : " f"{len(unmatched_patterns2)} *\n"
        )
        expected_result += f"* number actual log records  : {len(msgs_arg)} *\n"
        expected_result += f"* number actual unmatched    : {len(unmatched_msgs2)} *\n"
        expected_result += f"* number matched records     : {len(matched_msgs2)} *\n"

        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        for pattern in unmatched_patterns2:
            expected_result += f"('contention_0', 10, '{pattern}')\n"

        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        for msg in unmatched_msgs2:
            expected_result += f"('contention_0', 10, '{msg}')\n"

        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"

        for msg in matched_msgs2:
            expected_result += f"('contention_0', 10, '{msg}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_log_verifier_same_len_fullmatch
    ####################################################################
    msgs = ["msg1", "msg2", "msg3"]
    msg_perms = it.permutations(msgs, 3)
    msg_combos = mi.collapse(
        map(
            lambda mp: map(lambda n: it.product(mp[0:n], repeat=n), range(4)), msg_perms
        ),
        base_type=tuple,
    )
    msg_combos_list2 = sorted(set(msg_combos), key=lambda x: (len(x), x))

    patterns = (
        "msg0",
        "msg1",
        "msg2",
        "msg3",
        "msg[12]{1}",
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
    pattern_combos_list2 = sorted(set(pattern_combos), key=lambda x: (len(x), x))

    # @pytest.mark.parametrize("msgs_arg", msg_combos_list2)
    # @pytest.mark.parametrize("patterns_arg", pattern_combos_list2)
    @pytest.mark.parametrize("msgs_arg", [("msg2", "msg1")])
    @pytest.mark.parametrize("patterns_arg", [("msg[123]{1}",)])
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
        print(f"\n{msgs_arg=}\n{patterns_arg=}")
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

        @dataclass
        class ItemTracker:
            item: str
            claimed: bool
            potential_matches: list[int]
            potential_matches2: set[str]

        pattern_array: dict[int, ItemTracker] = {}
        msg_array: dict[int, ItemTracker] = {}

        def build_search_array(
            search_array: dict[int, ItemTracker],
            search_args: Iterable[tuple[str]],
            target_args: Iterable[tuple[str]],
            matched_array: dict[str, set[str]],
        ) -> None:
            for idx in range(len(search_args)):
                search_arg = search_args[idx]
                potential_matches = []
                potential_matches2 = set()

                for idx2, target_arg in enumerate(target_args):
                    if target_arg in matched_array[search_arg]:
                        potential_matches.append(idx2)
                        potential_matches2 |= {target_arg}

                search_array[idx] = ItemTracker(
                    item=search_arg,
                    claimed=False,
                    potential_matches=potential_matches.copy(),
                    potential_matches2=potential_matches2.copy(),
                )

        build_search_array(
            search_array=pattern_array,
            search_args=patterns_arg,
            target_args=msgs_arg,
            matched_array=matched_msg_array,
        )
        build_search_array(
            search_array=msg_array,
            search_args=msgs_arg,
            target_args=patterns_arg,
            matched_array=matched_pattern_array,
        )

        def make_claims(
            search_array: dict[int, ItemTracker],
            target_array: dict[int, ItemTracker],
            min_count: int,
        ) -> int:
            for idx in search_array.keys():
                potential_matches = search_array[idx].potential_matches
                if (
                    not search_array[idx].claimed
                    and len(potential_matches) == min_count
                ):
                    for idx2 in potential_matches:
                        if not target_array[idx2].claimed:
                            target_array[idx2].claimed = True
                            target_array[idx2].potential_matches = []
                            search_array[idx].claimed = True
                            search_array[idx].potential_matches = []

                            for clean_array, rem_idx in zip(
                                [search_array, target_array], [idx2, idx]
                            ):
                                for idx3 in clean_array.keys():
                                    if rem_idx in clean_array[idx3].potential_matches:
                                        clean_array[idx3].potential_matches.remove(
                                            rem_idx
                                        )
                                        if len(clean_array[idx3].potential_matches) > 0:
                                            min_count = min(
                                                min_count,
                                                len(
                                                    clean_array[idx3].potential_matches
                                                ),
                                            )
                            break
                    search_array[idx].potential_matches = []
            return min_count

        while True:
            min_count = 0
            for check_array in [pattern_array, msg_array]:
                for key, item in check_array.items():
                    len_potentials = len(item.potential_matches)
                    if len_potentials > 0:
                        if min_count == 0:
                            min_count = len_potentials
                        else:
                            min_count = min(min_count, len_potentials)

            if min_count == 0:
                break

            min_count = make_claims(
                search_array=pattern_array,
                target_array=msg_array,
                min_count=min_count,
            )
            make_claims(
                search_array=msg_array,
                target_array=pattern_array,
                min_count=min_count,
            )

        unmatched_patterns: list[str] = []
        # unmatched_patterns2: list[str] = []
        matched_patterns: list[str] = []
        # matched_patterns2: list[str] = []

        unmatched_msgs: list[str] = []
        # unmatched_msgs2: list[str] = []
        matched_msgs: list[str] = []
        # matched_msgs2: list[str] = []

        for match_array, matched_list, unmatched_list in zip(
            [pattern_array, msg_array],
            [matched_patterns, matched_msgs],
            [unmatched_patterns, unmatched_msgs],
        ):
            for idx in match_array.keys():
                if match_array[idx].claimed:
                    matched_list.append(match_array[idx].item)
                else:
                    unmatched_list.append(match_array[idx].item)

        matched_patterns2 = matched_patterns.copy()
        unmatched_patterns2 = unmatched_patterns.copy()

        matched_msgs2 = matched_msgs.copy()
        unmatched_msgs2 = unmatched_msgs.copy()

        if msgs_arg:
            msgs_arg_list = list(msgs_arg)
        else:
            msgs_arg_list = []

        if patterns_arg:
            patterns_arg_list = list(patterns_arg)
        else:
            patterns_arg_list = []

        def find_x_y_x(arg_list: list[str]) -> str:
            if len(arg_list) == 3:
                for arg in arg_list:
                    if arg_list.count(arg) > 1 and arg == arg_list[2]:
                        return arg
            return ""

        sort_x_y_x_msg = find_x_y_x(msgs_arg_list)
        sort_x_y_x_pattern = find_x_y_x(patterns_arg_list)

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

        test_matched_found_msgs_list = []
        test_unmatched_found_msgs_list = []
        test_matched_found_patterns_list = []
        test_unmatched_found_patterns_list = []

        if patterns_arg and msgs_arg:

            def find_combo_matches(
                item_array: dict[int, ItemTracker],
                items_arg_list: list[str],
                test_matched_found_items_list: list[list[str]],
                test_unmatched_found_items_list: list[list[str]],
                sort_x_y_x_item: str,
            ):
                for perm_idx in it.permutations(range(len(item_array))):
                    item_combo_lists = []
                    for idx in perm_idx:
                        # if len(item_array["potential_finds2"].iloc[idx]) > 0:
                        if len(item_array[idx].potential_matches2) > 0:
                            c_items = []
                            for potential_find_item in item_array[
                                idx
                            ].potential_matches2:
                                c_items.append(potential_find_item)
                            item_combo_lists.append(c_items)
                        else:
                            item_combo_lists.append(["none"])
                    item_prods = ""
                    if len(item_combo_lists) == 1:
                        item_prods = it.product(
                            item_combo_lists[0],
                        )
                    elif len(item_combo_lists) == 2:
                        item_prods = it.product(
                            item_combo_lists[0],
                            item_combo_lists[1],
                        )
                    elif len(item_combo_lists) == 3:
                        item_prods = it.product(
                            item_combo_lists[0],
                            item_combo_lists[1],
                            item_combo_lists[2],
                        )
                    item_prods = list(item_prods)
                    for item_prod in item_prods:
                        test_found_items = []
                        items_arg_copy = items_arg_list.copy()
                        for item in item_prod:
                            if item in items_arg_copy:
                                test_found_items.append(item)
                                items_arg_copy.remove(item)
                        # test_found_items.sort(key=items_arg.index)
                        test_found_items = sort_items(
                            test_found_items,
                            items_arg_list,
                            sort_x_y_x_item,
                        )
                        items_arg_copy = sort_items(
                            items_arg_copy,
                            items_arg_list,
                            sort_x_y_x_item,
                        )
                        test_matched_found_items_list.append(test_found_items)
                        test_unmatched_found_items_list.append(items_arg_copy.copy())

            find_combo_matches(
                item_array=pattern_array,
                items_arg_list=msgs_arg_list,
                test_matched_found_items_list=test_matched_found_msgs_list,
                test_unmatched_found_items_list=test_unmatched_found_msgs_list,
                sort_x_y_x_item=sort_x_y_x_msg,
            )

            find_combo_matches(
                item_array=msg_array,
                items_arg_list=patterns_arg_list,
                test_matched_found_items_list=test_matched_found_patterns_list,
                test_unmatched_found_items_list=test_unmatched_found_patterns_list,
                sort_x_y_x_item=sort_x_y_x_pattern,
            )

        unmatched_msgs = sort_items(unmatched_msgs, msgs_arg_list, sort_x_y_x_msg)
        matched_msgs = sort_items(matched_msgs, msgs_arg_list, sort_x_y_x_msg)

        unmatched_patterns = sort_items(
            unmatched_patterns, patterns_arg_list, sort_x_y_x_pattern
        )
        matched_patterns = sort_items(
            matched_patterns, patterns_arg_list, sort_x_y_x_pattern
        )

        def compare_combos(
            test_matched_found_items_list: list[list[str]],
            test_unmatched_found_items_list: list[list[str]],
            matched_items: list[str],
            unmatched_items: list[str],
            items_arg_list: list[str],
        ):
            num_matched_items_agreed = 0
            num_matched_items_not_agreed = 0
            num_unmatched_items_agreed = 0
            num_unmatched_items_not_agreed = 0
            if patterns_arg_list and msgs_arg_list:
                for test_unmatched_found_items in test_unmatched_found_items_list:
                    if test_unmatched_found_items == unmatched_items:
                        num_unmatched_items_agreed += 1
                    else:
                        num_unmatched_items_not_agreed += 1

                for test_matched_found_items in test_matched_found_items_list:
                    if test_matched_found_items == matched_items:
                        num_matched_items_agreed += 1
                    else:
                        num_matched_items_not_agreed += 1
                        assert len(test_matched_found_items) <= len(matched_items)
            else:
                if not matched_items and unmatched_items == items_arg_list:
                    num_matched_items_agreed = 1
                    num_matched_items_not_agreed = 0
                    num_unmatched_items_agreed = 1
                    num_unmatched_items_not_agreed = 0

            return (
                num_matched_items_agreed,
                num_matched_items_not_agreed,
                num_unmatched_items_agreed,
                num_unmatched_items_not_agreed,
            )

        (
            num_matched_msgs_agreed,
            num_matched_msgs_not_agreed,
            num_unmatched_msgs_agreed,
            num_unmatched_msgs_not_agreed,
        ) = compare_combos(
            test_matched_found_items_list=test_matched_found_msgs_list,
            test_unmatched_found_items_list=test_unmatched_found_msgs_list,
            matched_items=matched_msgs,
            unmatched_items=unmatched_msgs,
            items_arg_list=msgs_arg_list,
        )

        (
            num_matched_patterns_agreed,
            num_matched_patterns_not_agreed,
            num_unmatched_patterns_agreed,
            num_unmatched_patterns_not_agreed,
        ) = compare_combos(
            test_matched_found_items_list=test_matched_found_patterns_list,
            test_unmatched_found_items_list=test_unmatched_found_patterns_list,
            matched_items=matched_patterns,
            unmatched_items=unmatched_patterns,
            items_arg_list=patterns_arg_list,
        )

        assert num_unmatched_msgs_agreed
        assert num_matched_msgs_agreed

        assert num_unmatched_patterns_agreed
        assert num_matched_patterns_agreed

        ################################################################
        # add patterns and issue log msgs
        ################################################################
        caplog.clear()

        log_name = "contention_0"
        t_logger = logging.getLogger(log_name)
        log_ver = LogVer(log_name=log_name)

        fullmatch_tf_arg = True
        for pattern in patterns_arg:
            log_ver.add_msg(log_msg=pattern, fullmatch=fullmatch_tf_arg)

        for msg in msgs_arg:
            t_logger.debug(msg)

        log_ver.print_match_results(log_results := log_ver.get_match_results(caplog))

        expected_result = "\n"
        expected_result += f"{msgs_arg=}\n"
        expected_result += f"{patterns_arg=}\n"

        expected_result += "\n"
        expected_result += "**********************************\n"
        expected_result += f"* number expected log records: {len(patterns_arg)} *\n"
        expected_result += (
            f"* number expected unmatched  : " f"{len(unmatched_patterns2)} *\n"
        )
        expected_result += f"* number actual log records  : {len(msgs_arg)} *\n"
        expected_result += f"* number actual unmatched    : {len(unmatched_msgs2)} *\n"
        expected_result += f"* number matched records     : {len(matched_msgs2)} *\n"

        expected_result += "**********************************\n"
        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched expected records    *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        for pattern in unmatched_patterns2:
            expected_result += f"('contention_0', 10, '{pattern}')\n"

        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* unmatched actual records      *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"
        for msg in unmatched_msgs2:
            expected_result += f"('contention_0', 10, '{msg}')\n"

        expected_result += "\n"
        expected_result += "*********************************\n"
        expected_result += "* matched records               *\n"
        expected_result += "* (logger name, level, message) *\n"
        expected_result += "*********************************\n"

        for msg in matched_msgs2:
            expected_result += f"('contention_0', 10, '{msg}')\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

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

    @pytest.mark.parametrize("num_a_msg_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_a_pat_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_a_fm_pat_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_aa_msg_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_aa_pat_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_aa_fm_pat_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_aaa_msg_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_aaa_pat_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_aaa_fm_pat_arg", [0, 1, 2])
    # @pytest.mark.parametrize("num_a_msg_arg", [2])
    # @pytest.mark.parametrize("num_a_pat_arg", [1])
    # @pytest.mark.parametrize("num_a_fm_pat_arg", [0])
    # @pytest.mark.parametrize("num_aa_msg_arg", [0])
    # @pytest.mark.parametrize("num_aa_pat_arg", [0])
    # @pytest.mark.parametrize("num_aa_fm_pat_arg", [0])
    # @pytest.mark.parametrize("num_aaa_msg_arg", [0])
    # @pytest.mark.parametrize("num_aaa_pat_arg", [0])
    # @pytest.mark.parametrize("num_aaa_fm_pat_arg", [0])
    def test_log_verifier_scratch(
        self,
        num_a_msg_arg: int,
        num_a_pat_arg: int,
        num_a_fm_pat_arg: int,
        num_aa_msg_arg: int,
        num_aa_pat_arg: int,
        num_aa_fm_pat_arg: int,
        num_aaa_msg_arg: int,
        num_aaa_pat_arg: int,
        num_aaa_fm_pat_arg: int,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier time match.

        Args:
            num_a_msg_arg: number of a log msgs to issue
            num_a_pat_arg: number of a patterns to use
            num_a_fm_pat_arg: number of a fullmatch patterns to use
            num_aa_msg_arg: number of aa log msgs to issue
            num_aa_pat_arg: number of aa patterns to use
            num_aa_fm_pat_arg: number of aa fullmatch patterns to use
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        test_log_ver = TestLogVerification(
            log_name="scratch_1", capsys_to_use=capsys, caplog_to_use=caplog
        )
        ################################################################
        # issue log msgs
        ################################################################
        for _ in range(num_a_msg_arg):
            test_log_ver.issue_log_msg("a")

        for _ in range(num_aa_msg_arg):
            test_log_ver.issue_log_msg("aa")

        for _ in range(num_aaa_msg_arg):
            test_log_ver.issue_log_msg("aaa")

        ################################################################
        # add patterns
        ################################################################
        for _ in range(num_a_pat_arg):
            test_log_ver.add_pattern("a")

        for _ in range(num_a_fm_pat_arg):
            test_log_ver.add_pattern("a", fullmatch=True)

        for _ in range(num_aa_pat_arg):
            test_log_ver.add_pattern("aa")

        for _ in range(num_aa_fm_pat_arg):
            test_log_ver.add_pattern("aa", fullmatch=True)

        for _ in range(num_aaa_pat_arg):
            test_log_ver.add_pattern("aaa")

        for _ in range(num_aaa_fm_pat_arg):
            test_log_ver.add_pattern("aaa", fullmatch=True)

        @dataclass
        class NumExpectedAccumulator:
            num_surplus_match_patterns: int = 0
            num_unmatched_patterns: int = 0
            num_unmatched_log_msgs: int = 0
            num_matched_log_msgs: int = 0

        def calc_expected_values(
            num_exp_accumulator: NumExpectedAccumulator,
            num_match_patterns: int,
            num_fullmatch_patterns: int,
            num_log_msgs,
        ) -> None:
            input_surplus_match_patterns = (
                num_exp_accumulator.num_surplus_match_patterns
            )
            num_patterns = (
                input_surplus_match_patterns
                + num_match_patterns
                + num_fullmatch_patterns
            )
            num_surplus_both_patterns = max(0, (num_patterns - num_log_msgs))
            num_surplus_fullmatch_patterns = max(
                0, (num_fullmatch_patterns - num_log_msgs)
            )
            num_surplus_match_patterns = max(
                0, (num_surplus_both_patterns - num_surplus_fullmatch_patterns)
            )

            num_exp_accumulator.num_surplus_match_patterns = num_surplus_match_patterns
            num_exp_accumulator.num_unmatched_patterns = (
                num_exp_accumulator.num_unmatched_patterns
                + num_surplus_both_patterns
                - input_surplus_match_patterns
            )
            num_exp_accumulator.num_unmatched_log_msgs += max(
                0, (num_log_msgs - num_patterns)
            )
            num_exp_accumulator.num_matched_log_msgs += min(num_log_msgs, num_patterns)

        ################################################################
        # calculate expected match numbers
        ################################################################
        num_exp_accumulator = NumExpectedAccumulator()
        calc_expected_values(
            num_exp_accumulator=num_exp_accumulator,
            num_match_patterns=num_a_pat_arg,
            num_fullmatch_patterns=num_a_fm_pat_arg,
            num_log_msgs=num_a_msg_arg,
        )

        calc_expected_values(
            num_exp_accumulator=num_exp_accumulator,
            num_match_patterns=num_aa_pat_arg,
            num_fullmatch_patterns=num_aa_fm_pat_arg,
            num_log_msgs=num_aa_msg_arg,
        )

        calc_expected_values(
            num_exp_accumulator=num_exp_accumulator,
            num_match_patterns=num_aaa_pat_arg,
            num_fullmatch_patterns=num_aaa_fm_pat_arg,
            num_log_msgs=num_aaa_msg_arg,
        )

        test_log_ver.verify_results(
            exp_num_unmatched_patterns=num_exp_accumulator.num_unmatched_patterns,
            exp_num_unmatched_log_msgs=num_exp_accumulator.num_unmatched_log_msgs,
            exp_num_matched_log_msgs=num_exp_accumulator.num_matched_log_msgs,
        )

        # log_results = test_log_ver.log_ver.get_match_results(caplog)
        # test_log_ver.log_ver.print_match_results(log_results)
