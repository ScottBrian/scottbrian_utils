"""test_log_verifier.py module."""

########################################################################
# Standard Library
########################################################################
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum, auto
import itertools as it
import more_itertools as mi
import logging
import numpy as np
import datetime
import re

import threading
import time
from typing import Optional, Union
import warnings

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.log_verifier import LogVer
from scottbrian_utils.log_verifier import MatchResults
from scottbrian_utils.log_verifier import (
    UnmatchedExpectedMessages,
    UnmatchedActualMessages,
    UnmatchedPatterns,
    UnmatchedLogMessages,
)
from scottbrian_utils.time_hdr import (
    get_datetime_match_string,
    timedelta_match_string,
)

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


class LogVerifyType(Enum):
    FullVerify = auto()
    IgnoreUnmatchedLogMsgs = auto()
    SkipVerFullPrint = auto()


@dataclass(order=True)
class LogItemDescriptor:
    item: str
    log_name: str
    level: int
    fullmatch: bool = False
    c_pattern: re.Pattern[str] = ""


@dataclass
class LogSectionLineItem:
    log_name: str
    level: int
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
    unmatched_patterns: list[LogItemDescriptor] = field(default_factory=list)
    matched_patterns: list[LogItemDescriptor] = field(default_factory=list)
    unmatched_log_msgs: list[LogItemDescriptor] = field(default_factory=list)
    matched_log_msgs: list[LogItemDescriptor] = field(default_factory=list)


@dataclass
class ItemStats:
    num_items: int = 0
    num_matched_items: int = 0
    num_unmatched_items: int = 0


@dataclass
class VerResult:
    unmatched_patterns: bool = False
    unmatched_log_msgs: bool = False
    matched_log_msgs: bool = False


class TestLogVerification:
    """Verify the log output."""

    def __init__(
        self,
        log_names: list[str],
        capsys_to_use: pytest.CaptureFixture[str],
        caplog_to_use: pytest.LogCaptureFixture,
        level: int = logging.DEBUG,
    ):
        """Initialize the test log verification.

        Args:
            log_names: log names to use
            capsys_to_use: pytest CaptureFixture for syslog
            caplog_to_use: pytest LogCaptureFixture for log messages
            level: specifies the log level

        """
        self.log_name: str = log_names[0]
        self.log_names: list[str] = log_names
        self.capsys_to_use = capsys_to_use
        self.caplog_to_use = caplog_to_use
        self.level = level
        self.loggers: dict[str, logging.Logger] = {}
        self.patterns: list[LogItemDescriptor] = []
        self.log_msgs: list[LogItemDescriptor] = []

        self.matches_array: list[np.array] = []

        for log_name in log_names:
            self.loggers[log_name] = logging.getLogger(log_name)
            self.loggers[log_name].setLevel(level)
        self.log_ver = LogVer(log_name=log_names[0])

        self.stats: dict[str, ItemStats] = {}
        self.match_scenario_found: bool = False
        self.matched_scenario: LogVerScenario = LogVerScenario()
        self.capsys_stats_hdr: str = ""
        self.capsys_stats_lines: list[str] = []
        self.capsys_sections: dict[str, LogSection] = {}

        self.captured_elapsed_time_lines: list[str] = []
        self.captured_pattern_stats_line: str = ""
        self.captured_log_msgs_stats_line: str = ""
        self.captured_num_matches: int = 0

        self.log_results: MatchResults = MatchResults()

        self.print_matched_arg = None
        self.print_matched = True

        self.start_time = 0

    def issue_log_msg(
        self,
        log_msg: str,
        level: int = logging.DEBUG,
        log_name: Optional[str] = None,
    ):
        if log_name is None:
            log_name = self.log_name
        self.loggers[log_name].log(level, log_msg)

        # add the log_msg to track only if it was logged per level
        if self.level <= level:
            self.log_msgs.append(
                LogItemDescriptor(
                    log_name=log_name,
                    level=level,
                    item=log_msg,
                )
            )

    def add_pattern(
        self,
        pattern: str,
        level: int = logging.DEBUG,
        log_name: Optional[str] = None,
        fullmatch: bool = False,
    ) -> LogItemDescriptor:
        if log_name is None:
            log_name = self.log_name
        self.log_ver.add_pattern(
            pattern=pattern, level=level, log_name=log_name, fullmatch=fullmatch
        )
        ret_pattern = LogItemDescriptor(
            log_name=log_name,
            level=level,
            item=pattern,
            c_pattern=re.compile(pattern),
            fullmatch=fullmatch,
        )
        self.patterns.append(ret_pattern)

        return ret_pattern

    def verify_captured(self, expected_result: str):
        """Verify the captured match results.

        Args:
            expected_result: the string of expected results

        """
        captured_capsys = self.capsys_to_use.readouterr().out
        captured_lines = captured_capsys.split("\n")
        expected_lines = expected_result.split("\n")

        dt_format_1 = get_datetime_match_string(format_str="%a %b %d %Y %H:%M:%S")
        start_pattern_regex = re.compile(f"Start: {dt_format_1}")
        end_pattern_regex = re.compile(f"End: {dt_format_1}")

        elapsed_time_pattern_regex = re.compile(
            f"Elapsed time: {timedelta_match_string}"
        )

        assert len(captured_lines) == len(expected_lines)
        assert len(captured_lines) > 6

        for idx in range(4):
            assert expected_lines[idx] == captured_lines[idx]

        assert start_pattern_regex.fullmatch(expected_lines[4])
        print(f"{start_pattern_regex}")
        print(f"{captured_lines[4]}")
        assert end_pattern_regex.fullmatch(expected_lines[5])
        assert elapsed_time_pattern_regex.fullmatch(expected_lines[6])

        for idx in range(7, len(captured_lines)):
            assert expected_lines[idx] == captured_lines[idx]

    def verify_results(
        self,
        print_only: bool = False,
        print_matched: Optional[bool] = None,
        exp_num_unmatched_patterns: Optional[int] = None,
        exp_unmatched_patterns: Optional[list[LogItemDescriptor]] = None,
        exp_num_unmatched_log_msgs: Optional[int] = None,
        exp_num_matched_log_msgs: Optional[int] = None,
    ) -> None:
        """Verify the log records.

        Args:
            print_only: specifies to printy the results without
                performing verification
            print_matched: specifies whether to print the matched
                records. If no, the matched records output will be
                supressed.
            exp_num_unmatched_patterns: number of unmatched patterns
                that are expected
            exp_unmatched_patterns: list of patterns that are expected
                to be unmatched
            exp_num_unmatched_log_msgs: number of unmatched log messages
                that are expected
            exp_num_matched_log_msgs: number of matched log messages
                that are expected
        """
        self.start_time = time.time()

        if print_only:
            # get log results and print them
            self.log_results = self.log_ver.get_match_results(self.caplog_to_use)
            if print_matched is None:
                self.log_ver.print_match_results(self.log_results)
            else:
                self.log_ver.print_match_results(
                    self.log_results, print_matched=print_matched
                )
            return

        self.print_matched_arg = print_matched
        if print_matched:
            self.print_matched = True
        else:
            self.print_matched = False

        self.build_ver_record()

        if exp_num_unmatched_patterns is not None:
            assert (
                self.stats["patterns"].num_unmatched_items == exp_num_unmatched_patterns
            )

        if exp_unmatched_patterns is not None:
            assert self.match_scenario_found
            assert len(self.matched_scenario.unmatched_patterns) == len(
                exp_unmatched_patterns
            )
            assert sorted(exp_unmatched_patterns) == sorted(
                self.matched_scenario.unmatched_patterns
            )

        if exp_num_unmatched_log_msgs is not None:
            assert (
                self.stats["log_msgs"].num_unmatched_items == exp_num_unmatched_log_msgs
            )

        if exp_num_matched_log_msgs is not None:
            assert self.stats["log_msgs"].num_matched_items == exp_num_matched_log_msgs

        patterns_stats_line = (
            f"patterns "
            f"{self.stats['patterns'].num_items:>8} "
            f"{self.stats['patterns'].num_matched_items:>8} "
            f"{self.stats['patterns'].num_unmatched_items:>10}"
        )

        log_msgs_stats_line = (
            f"log_msgs "
            f"{self.stats['log_msgs'].num_items:>8} "
            f"{self.stats['log_msgs'].num_matched_items:>8} "
            f"{self.stats['log_msgs'].num_unmatched_items:>10}"
        )

        assert self.captured_pattern_stats_line == patterns_stats_line
        assert self.captured_log_msgs_stats_line == log_msgs_stats_line

        if self.stats["patterns"].num_unmatched_items:
            exp_err_msg = (
                f'There (is|are) {self.stats["patterns"].num_unmatched_items} '
                f"pattern[s]? that did not match any log messages."
            )
            with pytest.raises(UnmatchedPatterns, match=exp_err_msg):
                self.log_ver.verify_match_results(self.log_results)
        elif self.stats["log_msgs"].num_unmatched_items:
            exp_err_msg = (
                f'There (is|are) {self.stats["log_msgs"].num_unmatched_items} '
                "log message[s]? that did not get matched by any patterns."
            )
            with pytest.raises(UnmatchedLogMessages, match=exp_err_msg):
                self.log_ver.verify_match_results(self.log_results)
        else:
            self.log_ver.verify_match_results(self.log_results)

        assert self.match_scenario_found

        for line in self.captured_elapsed_time_lines:
            print(line)

    def verify_scenario(self, scenario: LogVerScenario) -> bool:
        ver_result = VerResult()
        if self.verify_lines(
            item_text="pattern",
            unmatched_items=scenario.unmatched_patterns,
            matched_items=scenario.matched_patterns,
            log_section=self.capsys_sections["unmatched_patterns"],
            matched_section=False,
        ):
            ver_result.unmatched_patterns = True

        # logger.debug(f"verify_scenario calling verify_lines 2")
        if self.verify_lines(
            item_text="log_msg",
            unmatched_items=scenario.unmatched_log_msgs,
            matched_items=scenario.matched_log_msgs,
            log_section=self.capsys_sections["unmatched_log_msgs"],
            matched_section=False,
        ):
            ver_result.unmatched_log_msgs = True

        if self.verify_lines(
            item_text="log_msg",
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
            return True
        else:
            return False

    def verify_lines(
        self,
        item_text: str,
        unmatched_items: list[LogItemDescriptor],
        matched_items: list[LogItemDescriptor],
        log_section: LogSection,
        matched_section: bool,
    ) -> bool:
        exp_records = True
        if matched_section:
            exp_records = False
            if len(matched_items) == 0 or not self.print_matched:
                assert len(log_section.line_items) == 0
                return True
            else:
                for matched_item in matched_items:
                    unmatched_found = False
                    for unmatched_item in unmatched_items:
                        if (
                            matched_item.item == unmatched_item.item
                            and matched_item.log_name == unmatched_item.log_name
                            and matched_item.level == unmatched_item.level
                        ):
                            unmatched_found = True
                            break
                    if not unmatched_found:
                        exp_records = True
                        break
        else:
            if len(unmatched_items) == 0:
                assert len(log_section.line_items) == 0
                return True
            else:
                assert len(log_section.line_items) > 0

        max_log_name_len = 0
        max_log_msg_len = 0
        if matched_section:
            for item in matched_items:
                max_log_name_len = max(max_log_name_len, len(item.log_name))
                max_log_msg_len = max(max_log_msg_len, len(item.item))
        else:
            for item in unmatched_items:
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
                + " level"
                + " "
                + " " * (max_log_msg_len - len(item_text))
                + item_text
                + fullmatch_text
                + "  records"
                + "  matched"
                + "  unmatched"
            )
            if log_section.hdr_line != expected_hdr_line:
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
                    return False
                if line_item.num_actual_unmatches != line_item.num_counted_unmatched:
                    return False
        return True

    def build_ver_record(self):
        self.get_ver_output_lines()
        self.build_scenarios()

    def get_ver_output_lines(self):
        results_asterisks = "************************************************"
        results_line = "*             log verifier results             *"
        dt_format_1 = get_datetime_match_string(format_str="%a %b %d %Y %H:%M:%S")
        start_pattern_regex = re.compile(f"Start: {dt_format_1}")
        end_pattern_regex = re.compile(f"End: {dt_format_1}")

        elapsed_time_pattern_regex = re.compile(
            f"Elapsed time: {timedelta_match_string}"
        )

        stats_asterisks = "************************************************"
        stats_line = "*                summary stats                 *"

        unmatched_patterns_hdr_line = "* unmatched patterns: *"
        unmatched_log_msgs_hdr_line = "* unmatched log_msgs: *"
        matched_log_msgs_hdr_line = "*  matched log_msgs:  *"

        # clear the capsys
        _ = self.capsys_to_use.readouterr().out

        # get log results and print them
        self.log_results = self.log_ver.get_match_results(self.caplog_to_use)
        if self.print_matched_arg is None:
            self.log_ver.print_match_results(self.log_results)
        else:
            self.log_ver.print_match_results(
                self.log_results, print_matched=self.print_matched_arg
            )

        captured_capsys = self.capsys_to_use.readouterr().out
        captured_lines = captured_capsys.split("\n")

        assert captured_lines[0] == ""
        assert captured_lines[1] == results_asterisks
        assert captured_lines[2] == results_line
        assert captured_lines[3] == results_asterisks
        assert start_pattern_regex.fullmatch(captured_lines[4])
        assert end_pattern_regex.fullmatch(captured_lines[5])
        assert elapsed_time_pattern_regex.fullmatch(captured_lines[6])

        assert captured_lines[7] == ""
        assert captured_lines[8] == stats_asterisks
        assert captured_lines[9] == stats_line
        assert captured_lines[10] == stats_asterisks
        assert captured_lines[11] == "    type  records  matched  unmatched"

        self.captured_elapsed_time_lines = captured_lines[0:7]

        self.captured_pattern_stats_line = captured_lines[12]
        self.captured_log_msgs_stats_line = captured_lines[13]
        split_log_msgs_stats = self.captured_log_msgs_stats_line.split()
        self.captured_num_matches = int(split_log_msgs_stats[2])

        section_item = self.get_section(
            start_idx=15,
            captured_lines=captured_lines,
            section_hdr_line=unmatched_patterns_hdr_line,
            section_type="unmatched_patterns",
        )

        self.capsys_sections["unmatched_patterns"] = section_item

        section_item = self.get_section(
            start_idx=section_item.end_idx + 1,
            captured_lines=captured_lines,
            section_hdr_line=unmatched_log_msgs_hdr_line,
            section_type="unmatched_log_msgs",
        )

        self.capsys_sections["unmatched_log_msgs"] = section_item

        section_item = self.get_section(
            start_idx=section_item.end_idx + 1,
            captured_lines=captured_lines,
            section_hdr_line=matched_log_msgs_hdr_line,
            section_type="matched_log_msgs",
        )

        self.capsys_sections["matched_log_msgs"] = section_item

    def get_section(
        self,
        start_idx: int,
        captured_lines: list[str],
        section_hdr_line: str,
        section_type: str,
    ) -> LogSection:
        section_asterisks = "***********************"

        if section_type == "matched_log_msgs" and not self.print_matched:
            assert captured_lines[start_idx - 1] == ""
            assert len(captured_lines) == start_idx
            return LogSection(
                hdr_line="",
                start_idx=start_idx,
                end_idx=start_idx + 3,
                line_items={},
            )

        assert captured_lines[start_idx] == section_asterisks
        assert captured_lines[start_idx + 1] == section_hdr_line
        assert captured_lines[start_idx + 2] == section_asterisks

        if (
            (
                section_type == "unmatched_patterns"
                and captured_lines[start_idx + 3]
                == "*** no unmatched patterns found ***"
            )
            or (
                section_type == "unmatched_log_msgs"
                and captured_lines[start_idx + 3]
                == "*** no unmatched log messages found ***"
            )
            or (
                section_type == "matched_log_msgs"
                and captured_lines[start_idx + 3]
                == "*** no matched log messages found ***"
            )
        ):
            assert captured_lines[start_idx + 4] == ""
            return LogSection(
                hdr_line="",
                start_idx=start_idx,
                end_idx=start_idx + 4,
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
                # logger.critical(f"get_section 3: \n{captured_lines[idx-1:idx+2]}")
                return ret_section
            else:
                if section_type == "unmatched_patterns":
                    rsplit_actual = captured_lines[idx].rsplit(maxsplit=4)
                    fm_text = rsplit_actual[1]
                else:
                    rsplit_actual = captured_lines[idx].rsplit(maxsplit=3)
                    fm_text = ""

                lsplit_actual = rsplit_actual[0].split(maxsplit=2)

                log_name = lsplit_actual[0]
                level = int(lsplit_actual[1])

                item = lsplit_actual[2]

                key = item + fm_text

                num_items = int(rsplit_actual[-3])
                num_matches = int(rsplit_actual[-2])

                ret_section.line_items[key] = LogSectionLineItem(
                    log_name=log_name,
                    level=level,
                    item=item,
                    fullmatch=fm_text,
                    num_items=num_items,
                    num_actual_unmatches=num_items - num_matches,
                    num_actual_matches=num_matches,
                    num_counted_unmatched=0,
                    num_counted_matched=0,
                )

    def build_scenarios(self):

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
            self.match_scenario_found = True
            return

        max_matched_msgs = 0
        ################################################################
        # pre-build the matched arrays
        ################################################################
        self.build_match_arrays(patterns_len=patterns_len, log_msgs_len=log_msgs_len)
        min_desc_len = min(patterns_len, log_msgs_len)
        max_desc_len = max(patterns_len, log_msgs_len)

        self.match_scenario_found = False
        for idx, match_perm in enumerate(
            it.permutations(self.matches_array, min_desc_len)
        ):
            diag_match_array = np.array(match_perm)
            num_matched_items = np.trace(diag_match_array)
            max_matched_msgs = max(max_matched_msgs, num_matched_items)

            if num_matched_items == self.captured_num_matches:
                if self.match_scenario_found:
                    continue

                if patterns_len < log_msgs_len:
                    pattern_match_sel = np.diag(diag_match_array)
                    log_msg_match_sel = np.zeros(max_desc_len)

                    for idx2 in range(min_desc_len):
                        log_msg_match_sel[diag_match_array[idx2, -1]] = (
                            pattern_match_sel[idx2]
                        )
                else:
                    log_msg_match_sel = np.diag(diag_match_array)
                    pattern_match_sel = np.zeros(max_desc_len)

                    for idx2 in range(min_desc_len):
                        pattern_match_sel[diag_match_array[idx2, -1]] = (
                            log_msg_match_sel[idx2]
                        )

                staging_scenario: LogVerScenario = LogVerScenario(
                    unmatched_patterns=list(
                        it.compress(self.patterns, np.logical_not(pattern_match_sel))
                    ),
                    matched_patterns=list(
                        it.compress(self.patterns, pattern_match_sel)
                    ),
                    unmatched_log_msgs=list(
                        it.compress(self.log_msgs, np.logical_not(log_msg_match_sel))
                    ),
                    matched_log_msgs=list(
                        it.compress(self.log_msgs, log_msg_match_sel)
                    ),
                )

                # logger.debug(f"scenario: \n{staging_scenario}")
                if self.verify_scenario(scenario=staging_scenario):
                    self.match_scenario_found = True
                    self.matched_scenario = staging_scenario
            else:
                assert num_matched_items <= self.captured_num_matches

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
        def is_matched() -> int:
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
                and pattern_desc.level == log_msg_desc.level
            ):
                return 1
            return 0

        if patterns_len < log_msgs_len:
            for midx, log_msg_desc in enumerate(self.log_msgs):
                match_array = np.zeros(patterns_len + 1, dtype=np.int32)
                for idx, pattern_desc in enumerate(self.patterns):
                    match_array[idx] = is_matched()
                match_array[-1] = midx
                self.matches_array.append(match_array)
        else:
            for pidx, pattern_desc in enumerate(self.patterns):
                match_array = np.zeros(log_msgs_len + 1, dtype=np.int32)
                for idx, log_msg_desc in enumerate(self.log_msgs):
                    match_array[idx] = is_matched()
                match_array[-1] = pidx
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
        log_ver.add_pattern(pattern=log_msg)
        t_logger.debug(log_msg)
        match_results = log_ver.get_match_results(caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

        expected_result = "\n"
        expected_result += "************************************************\n"
        expected_result += "*             log verifier results             *\n"
        expected_result += "************************************************\n"
        expected_result += "Start: Thu Apr 11 2024 19:24:28\n"
        expected_result += "End: Thu Apr 11 2024 19:24:28\n"
        expected_result += "Elapsed time: 0:00:00.006002\n"
        expected_result += "\n"
        expected_result += "************************************************\n"
        expected_result += "*                summary stats                 *\n"
        expected_result += "************************************************\n"
        expected_result += "    type  records  matched  unmatched\n"
        expected_result += "patterns        1        1          0\n"
        expected_result += "log_msgs        1        1          0\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched patterns: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched patterns found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched log_msgs: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched log messages found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "*  matched log_msgs:  *\n"
        expected_result += "***********************\n"
        expected_result += f" log_name  level log_msg  records  matched  unmatched\n"
        expected_result += f"example_1     10   hello        1        1          0\n"

        test_log_ver = TestLogVerification(
            log_names=["example_1"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.verify_captured(expected_result=expected_result)

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
        log_ver.add_pattern(pattern=log_msg1)
        log_msg2 = "goodbye"
        log_ver.add_pattern(pattern=log_msg2)
        t_logger.debug(log_msg1)
        match_results = log_ver.get_match_results(caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        with pytest.raises(UnmatchedPatterns):
            log_ver.verify_match_results(match_results)

        expected_result = "\n"
        expected_result += "************************************************\n"
        expected_result += "*             log verifier results             *\n"
        expected_result += "************************************************\n"
        expected_result += "Start: Thu Apr 11 2024 19:24:28\n"
        expected_result += "End: Thu Apr 11 2024 19:24:28\n"
        expected_result += "Elapsed time: 0:00:00.006002\n"
        expected_result += "\n"
        expected_result += "************************************************\n"
        expected_result += "*                summary stats                 *\n"
        expected_result += "************************************************\n"
        expected_result += "    type  records  matched  unmatched\n"
        expected_result += "patterns        2        1          1\n"
        expected_result += "log_msgs        1        1          0\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched patterns: *\n"
        expected_result += "***********************\n"
        expected_result += (
            f" log_name  level pattern  fullmatch  records  matched  unmatched\n"
        )
        expected_result += (
            f"example_2     10 goodbye      False        1        0          1\n"
        )
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched log_msgs: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched log messages found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "*  matched log_msgs:  *\n"
        expected_result += "***********************\n"
        expected_result += f" log_name  level log_msg  records  matched  unmatched\n"
        expected_result += f"example_2     10   hello        1        1          0\n"

        test_log_ver = TestLogVerification(
            log_names=["example_2"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.verify_captured(expected_result=expected_result)

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
        log_ver.add_pattern(pattern=log_msg1)
        log_msg2 = "goodbye"
        t_logger.debug(log_msg1)
        t_logger.debug(log_msg2)
        log_ver.print_match_results(
            match_results := log_ver.get_match_results(caplog), print_matched=True
        )
        with pytest.raises(UnmatchedLogMessages):
            log_ver.verify_match_results(match_results)

        expected_result = "\n"
        expected_result += "************************************************\n"
        expected_result += "*             log verifier results             *\n"
        expected_result += "************************************************\n"
        expected_result += "Start: Thu Apr 11 2024 19:24:28\n"
        expected_result += "End: Thu Apr 11 2024 19:24:28\n"
        expected_result += "Elapsed time: 0:00:00.006002\n"
        expected_result += "\n"
        expected_result += "************************************************\n"
        expected_result += "*                summary stats                 *\n"
        expected_result += "************************************************\n"
        expected_result += "    type  records  matched  unmatched\n"
        expected_result += "patterns        1        1          0\n"
        expected_result += "log_msgs        2        1          1\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched patterns: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched patterns found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched log_msgs: *\n"
        expected_result += "***********************\n"
        expected_result += f" log_name  level log_msg  records  matched  unmatched\n"
        expected_result += f"example_3     10 goodbye        1        0          1\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "*  matched log_msgs:  *\n"
        expected_result += "***********************\n"
        expected_result += f" log_name  level log_msg  records  matched  unmatched\n"
        expected_result += f"example_3     10   hello        1        1          0\n"

        test_log_ver = TestLogVerification(
            log_names=["example_3"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.verify_captured(expected_result=expected_result)

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
        log_ver.add_pattern(pattern=log_msg1)
        log_msg2a = "goodbye"
        log_ver.add_pattern(pattern=log_msg2a)
        log_msg2b = "see you soon"
        t_logger.debug(log_msg1)
        t_logger.debug(log_msg2b)
        log_ver.print_match_results(
            match_results := log_ver.get_match_results(caplog), print_matched=True
        )
        with pytest.raises(UnmatchedPatterns):
            log_ver.verify_match_results(match_results)

        expected_result = "\n"
        expected_result += "************************************************\n"
        expected_result += "*             log verifier results             *\n"
        expected_result += "************************************************\n"
        expected_result += "Start: Thu Apr 11 2024 19:24:28\n"
        expected_result += "End: Thu Apr 11 2024 19:24:28\n"
        expected_result += "Elapsed time: 0:00:00.006002\n"
        expected_result += "\n"
        expected_result += "************************************************\n"
        expected_result += "*                summary stats                 *\n"
        expected_result += "************************************************\n"
        expected_result += "    type  records  matched  unmatched\n"
        expected_result += "patterns        2        1          1\n"
        expected_result += "log_msgs        2        1          1\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched patterns: *\n"
        expected_result += "***********************\n"
        expected_result += (
            f" log_name  level pattern  fullmatch  records  matched  unmatched\n"
        )
        expected_result += (
            f"example_4     10 goodbye      False        1        0          1\n"
        )
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched log_msgs: *\n"
        expected_result += "***********************\n"
        expected_result += (
            f" log_name  level      log_msg  records  matched  unmatched\n"
        )
        expected_result += (
            f"example_4     10 see you soon        1        0          1\n"
        )
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "*  matched log_msgs:  *\n"
        expected_result += "***********************\n"
        expected_result += f" log_name  level log_msg  records  matched  unmatched\n"
        expected_result += f"example_4     10   hello        1        1          0\n"

        test_log_ver = TestLogVerification(
            log_names=["example_4"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.verify_captured(expected_result=expected_result)

    ####################################################################
    # test_log_verifier_example5
    ####################################################################
    def test_log_verifier_example5(
        self, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test log_verifier example5 for add_pattern.

        Args:
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output

        """
        # add two log messages, each different level
        t_logger = logging.getLogger("example_5")
        log_ver = LogVer("example_5")
        log_msg1 = "hello"
        log_msg2 = "goodbye"
        log_ver.add_pattern(pattern=log_msg1)
        log_ver.add_pattern(pattern=log_msg2, level=logging.ERROR)
        t_logger.debug(log_msg1)
        t_logger.error(log_msg2)
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

        expected_result = "\n"
        expected_result += "************************************************\n"
        expected_result += "*             log verifier results             *\n"
        expected_result += "************************************************\n"
        expected_result += "Start: Thu Apr 11 2024 19:24:28\n"
        expected_result += "End: Thu Apr 11 2024 19:24:28\n"
        expected_result += "Elapsed time: 0:00:00.006002\n"
        expected_result += "\n"
        expected_result += "************************************************\n"
        expected_result += "*                summary stats                 *\n"
        expected_result += "************************************************\n"
        expected_result += "    type  records  matched  unmatched\n"
        expected_result += "patterns        2        2          0\n"
        expected_result += "log_msgs        2        2          0\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched patterns: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched patterns found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched log_msgs: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched log messages found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "*  matched log_msgs:  *\n"
        expected_result += "***********************\n"
        expected_result += f" log_name  level log_msg  records  matched  unmatched\n"
        expected_result += f"example_5     10   hello        1        1          0\n"
        expected_result += f"example_5     40 goodbye        1        1          0\n"

        test_log_ver = TestLogVerification(
            log_names=["example_5"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.verify_captured(expected_result=expected_result)


########################################################################
# TestLogVerBasic class
########################################################################
@pytest.mark.cover2
class TestLogVerBasic:
    """Test basic functions of LogVer."""

    ####################################################################
    # test_log_verifier_deprecation_warning
    ####################################################################
    def test_log_verifier_deprecation_warning(
        self,
    ) -> None:
        """Test log_verifier time match."""
        log_ver = LogVer(log_name="deprecation_warning")

        with warnings.catch_warnings(record=True) as w:
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")
            # Trigger a warning.
            log_ver.add_msg(log_msg="bad_msg")
            # Verify the warning
            assert len(w) == 1
            assert issubclass(w[-1].category, DeprecationWarning)
            assert "deprecated" in str(w[-1].message)

        with warnings.catch_warnings(record=True) as w:
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")
            # Trigger a warning.
            log_ver.verify_log_results(match_results=MatchResults())
            # Verify the warning
            assert len(w) == 1
            assert issubclass(w[-1].category, DeprecationWarning)
            assert "deprecated" in str(w[-1].message)

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
    # test_log_verifier_no_match1
    ####################################################################
    @pytest.mark.parametrize("num_patterns_arg", (0, 1, 2))
    @pytest.mark.parametrize("num_log_msgs_arg", (0, 1, 2))
    def test_log_verifier_no_match1(
        self,
        num_patterns_arg: int,
        num_log_msgs_arg: int,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier time match.

        Args:
            num_patterns_arg: number of patterns to add
            num_log_msgs_arg: number of log messages to issue
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        t_logger = logging.getLogger("no_match1")
        log_ver = LogVer(log_name="no_match1")

        for idx in range(num_patterns_arg):
            log_ver.add_pattern(pattern="a")

        for idx in range(num_log_msgs_arg):
            t_logger.debug("b")

        log_ver.print_match_results(
            match_results := log_ver.get_match_results(caplog), print_matched=True
        )

        # use deprecated verify_log_results to verify it still works
        # until we remove it
        if num_patterns_arg:
            with pytest.raises(UnmatchedExpectedMessages):
                log_ver.verify_log_results(match_results)
        elif num_log_msgs_arg:
            with pytest.raises(UnmatchedActualMessages):
                log_ver.verify_log_results(match_results)
        else:
            log_ver.verify_log_results(match_results)

        expected_result = "\n"
        expected_result += "************************************************\n"
        expected_result += "*             log verifier results             *\n"
        expected_result += "************************************************\n"
        expected_result += "Start: Thu Apr 11 2024 19:24:28\n"
        expected_result += "End: Thu Apr 11 2024 19:24:28\n"
        expected_result += "Elapsed time: 0:00:00.006002\n"
        expected_result += "\n"
        expected_result += "************************************************\n"
        expected_result += "*                summary stats                 *\n"
        expected_result += "************************************************\n"
        expected_result += "    type  records  matched  unmatched\n"
        expected_result += (
            f"patterns {num_patterns_arg:>8} {0:>8} {num_patterns_arg:>10}\n"
        )
        expected_result += (
            f"log_msgs {num_log_msgs_arg:>8} {0:>8} {num_log_msgs_arg:>10}\n"
        )
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched patterns: *\n"
        expected_result += "***********************\n"
        if num_patterns_arg:
            expected_result += (
                f" log_name  level pattern  fullmatch  records  matched  unmatched\n"
            )
            expected_result += (
                f"no_match1     10       a      False {num_patterns_arg:>8} {0:>8} "
                f"{num_patterns_arg:>10}\n"
            )
        else:
            expected_result += "*** no unmatched patterns found ***\n"

        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched log_msgs: *\n"
        expected_result += "***********************\n"
        if num_log_msgs_arg:
            expected_result += (
                f" log_name  level log_msg  records  matched  unmatched\n"
            )
            expected_result += (
                f"no_match1     10       b {num_log_msgs_arg:>8} {0:>8} "
                f"{num_log_msgs_arg:>10}\n"
            )
        else:
            expected_result += "*** no unmatched log messages found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "*  matched log_msgs:  *\n"
        expected_result += "***********************\n"
        expected_result += "*** no matched log messages found ***\n"

        test_log_ver = TestLogVerification(
            log_names=["no_match1"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.verify_captured(expected_result=expected_result)

    ####################################################################
    # test_log_verifier_no_match2
    ####################################################################
    @pytest.mark.parametrize("num_patterns_arg", (0, 1, 2))
    @pytest.mark.parametrize("num_log_msgs_arg", (0, 1, 2))
    def test_log_verifier_no_match2(
        self,
        num_patterns_arg: int,
        num_log_msgs_arg: int,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier time match.

        Args:
            num_patterns_arg: number of patterns to add
            num_log_msgs_arg: number of log messages to issue
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        caplog.clear()

        test_log_ver = TestLogVerification(
            log_names=["no_match2"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        for idx in range(num_patterns_arg):
            test_log_ver.add_pattern(pattern="a")

        for idx in range(num_log_msgs_arg):
            test_log_ver.issue_log_msg("b")

        ################################################################
        # verify results
        ################################################################
        exp_num_unmatched_patterns = num_patterns_arg
        exp_num_unmatched_log_msgs = num_log_msgs_arg
        exp_num_matched_log_msgs = 0

        test_log_ver.verify_results(
            print_only=True,
            print_matched=False,
            exp_num_unmatched_patterns=exp_num_unmatched_patterns,
            exp_num_unmatched_log_msgs=exp_num_unmatched_log_msgs,
            exp_num_matched_log_msgs=exp_num_matched_log_msgs,
        )

    ####################################################################
    # test_log_verifier_simple_match
    ####################################################################
    @pytest.mark.parametrize("simple_str_arg", ("a", "ab", "a1", "xyz123"))
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

        log_ver.add_pattern(pattern=simple_str_arg)
        t_logger.debug(simple_str_arg)
        log_ver.print_match_results(
            match_results := log_ver.get_match_results(caplog), print_matched=True
        )
        log_ver.verify_match_results(match_results)

        hdr_log_msg = "log_msg"
        hdr_log_msg_width = max(len(hdr_log_msg), len(simple_str_arg))

        expected_result = "\n"
        expected_result += "************************************************\n"
        expected_result += "*             log verifier results             *\n"
        expected_result += "************************************************\n"
        expected_result += "Start: Thu Apr 11 2024 19:24:28\n"
        expected_result += "End: Thu Apr 11 2024 19:24:28\n"
        expected_result += "Elapsed time: 0:00:00.006002\n"
        expected_result += "\n"
        expected_result += "************************************************\n"
        expected_result += "*                summary stats                 *\n"
        expected_result += "************************************************\n"
        expected_result += "    type  records  matched  unmatched\n"
        expected_result += "patterns        1        1          0\n"
        expected_result += "log_msgs        1        1          0\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched patterns: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched patterns found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched log_msgs: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched log messages found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "*  matched log_msgs:  *\n"
        expected_result += "***********************\n"
        expected_result += (
            f"    log_name  level {hdr_log_msg:>{hdr_log_msg_width}} "
            f" records  matched  unmatched\n"
        )
        expected_result += (
            f"simple_match     10 {simple_str_arg:>{hdr_log_msg_width}} "
            f"       1        1          0\n"
        )

        test_log_ver = TestLogVerification(
            log_names=["simple_match"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.verify_captured(expected_result=expected_result)

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
        ################################################################
        # add patterns and issue log msgs
        ################################################################
        caplog.clear()

        test_log_ver = TestLogVerification(
            log_names=["print_matched"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        log_msgs: list[str] = []
        for idx in range(num_msgs_arg):
            log_msgs.append(f"log_msg_{idx}")
            test_log_ver.add_pattern(pattern=log_msgs[idx])
            test_log_ver.issue_log_msg(log_msgs[idx])

        ################################################################
        # verify results
        ################################################################
        exp_num_unmatched_patterns = 0
        exp_num_unmatched_log_msgs = 0
        exp_num_matched_log_msgs = len(log_msgs)

        test_log_ver.verify_results(
            print_matched=print_matched_arg,
            exp_num_unmatched_patterns=exp_num_unmatched_patterns,
            exp_num_unmatched_log_msgs=exp_num_unmatched_log_msgs,
            exp_num_matched_log_msgs=exp_num_matched_log_msgs,
        )

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
        caplog.clear()

        test_log_ver = TestLogVerification(
            log_names=["fullmatch_0"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.add_pattern(pattern=double_str_arg[0])
        test_log_ver.add_pattern(pattern=double_str_arg[1])

        test_log_ver.issue_log_msg(double_str_arg[0])
        test_log_ver.issue_log_msg(double_str_arg[1])

        ################################################################
        # verify results
        ################################################################
        test_log_ver.verify_results(
            print_only=False,
            exp_num_unmatched_patterns=0,
            exp_num_unmatched_log_msgs=0,
            exp_num_matched_log_msgs=2,
        )

        ################################################################
        # step 1: use non-fullmatch in controlled way (reverse order
        # of issuing the log messages)
        # before re-design, this caused an error - should now be OK
        ################################################################
        caplog.clear()

        test_log_ver = TestLogVerification(
            log_names=["fullmatch_1"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.add_pattern(pattern=double_str_arg[0])
        test_log_ver.add_pattern(pattern=double_str_arg[1])

        test_log_ver.issue_log_msg(double_str_arg[1])
        test_log_ver.issue_log_msg(double_str_arg[0])

        ################################################################
        # verify results
        ################################################################
        test_log_ver.verify_results(
            print_only=False,
            exp_num_unmatched_patterns=0,
            exp_num_unmatched_log_msgs=0,
            exp_num_matched_log_msgs=2,
        )

        ################################################################
        # step 2: use fullmatch in controlled way - should succeed
        ################################################################
        caplog.clear()

        test_log_ver = TestLogVerification(
            log_names=["fullmatch_2"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.add_pattern(pattern=double_str_arg[0], fullmatch=True)
        test_log_ver.add_pattern(pattern=double_str_arg[1], fullmatch=True)

        test_log_ver.issue_log_msg(double_str_arg[0])
        test_log_ver.issue_log_msg(double_str_arg[1])

        ################################################################
        # verify results
        ################################################################
        test_log_ver.verify_results(
            print_only=False,
            exp_num_unmatched_patterns=0,
            exp_num_unmatched_log_msgs=0,
            exp_num_matched_log_msgs=2,
        )

        ################################################################
        # step 3: use fullmatch in error case and expect success
        ################################################################
        caplog.clear()

        test_log_ver = TestLogVerification(
            log_names=["fullmatch_3"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.add_pattern(pattern=double_str_arg[0], fullmatch=True)
        test_log_ver.add_pattern(pattern=double_str_arg[1], fullmatch=True)

        test_log_ver.issue_log_msg(double_str_arg[1])
        test_log_ver.issue_log_msg(double_str_arg[0])

        ################################################################
        # verify results
        ################################################################
        test_log_ver.verify_results(
            print_only=False,
            exp_num_unmatched_patterns=0,
            exp_num_unmatched_log_msgs=0,
            exp_num_matched_log_msgs=2,
        )

        ################################################################
        # step 4: use fullmatch and cause unmatched pattern failure
        ################################################################
        caplog.clear()

        unmatched_patterns: list[LogItemDescriptor] = []

        test_log_ver = TestLogVerification(
            log_names=["fullmatch_4"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        pattern_0 = test_log_ver.add_pattern(pattern=double_str_arg[0], fullmatch=True)
        test_log_ver.add_pattern(pattern=double_str_arg[1], fullmatch=True)

        unmatched_patterns.append(pattern_0)

        test_log_ver.issue_log_msg(double_str_arg[1])
        # test_log_ver.issue_log_msg(double_str_arg[0])

        ################################################################
        # verify results
        ################################################################
        test_log_ver.verify_results(
            print_only=False,
            exp_num_unmatched_patterns=1,
            exp_unmatched_patterns=unmatched_patterns,
            exp_num_unmatched_log_msgs=0,
            exp_num_matched_log_msgs=1,
        )

    ####################################################################
    # test_log_verifier_same_len_fullmatch
    ####################################################################
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

        ################################################################
        # add patterns and issue log msgs
        ################################################################
        caplog.clear()

        test_log_ver = TestLogVerification(
            log_names=["fullmatch_0"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        if add_pattern1_first_arg:
            test_log_ver.add_pattern(
                pattern=pattern1, fullmatch=pattern1_fullmatch_tf_arg
            )
            test_log_ver.add_pattern(
                pattern=pattern2, fullmatch=pattern2_fullmatch_tf_arg
            )
        else:
            test_log_ver.add_pattern(
                pattern=pattern2, fullmatch=pattern2_fullmatch_tf_arg
            )
            test_log_ver.add_pattern(
                pattern=pattern1, fullmatch=pattern1_fullmatch_tf_arg
            )

        if issue_msg1_first_arg:
            test_log_ver.issue_log_msg(msg1)
            test_log_ver.issue_log_msg(msg2)
        else:
            test_log_ver.issue_log_msg(msg2)
            test_log_ver.issue_log_msg(msg1)

        ################################################################
        # verify results
        ################################################################
        exp_num_unmatched_patterns = 0
        exp_num_unmatched_log_msgs = 0
        exp_num_matched_log_msgs = 2

        test_log_ver.verify_results(
            print_only=False,
            exp_num_unmatched_patterns=exp_num_unmatched_patterns,
            exp_num_unmatched_log_msgs=exp_num_unmatched_log_msgs,
            exp_num_matched_log_msgs=exp_num_matched_log_msgs,
        )

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
        log_ver.add_pattern(pattern=exp_msg, log_name="time_match")
        t_logger.debug(act_msg)
        log_ver.print_match_results(
            match_results := log_ver.get_match_results(caplog), print_matched=True
        )
        log_ver.verify_match_results(match_results)

        hdr_log_msg = "log_msg"
        hdr_log_msg_width = max(len(hdr_log_msg), len(act_msg))

        expected_result = "\n"
        expected_result += "************************************************\n"
        expected_result += "*             log verifier results             *\n"
        expected_result += "************************************************\n"
        expected_result += "Start: Thu Apr 11 2024 19:24:28\n"
        expected_result += "End: Thu Apr 11 2024 19:24:28\n"
        expected_result += "Elapsed time: 0:00:00.006002\n"
        expected_result += "\n"
        expected_result += "************************************************\n"
        expected_result += "*                summary stats                 *\n"
        expected_result += "************************************************\n"
        expected_result += "    type  records  matched  unmatched\n"
        expected_result += "patterns        1        1          0\n"
        expected_result += "log_msgs        1        1          0\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched patterns: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched patterns found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched log_msgs: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched log messages found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "*  matched log_msgs:  *\n"
        expected_result += "***********************\n"
        expected_result += (
            f"  log_name  level {hdr_log_msg:>{hdr_log_msg_width}} "
            f" records  matched  unmatched\n"
        )
        expected_result += (
            f"time_match     10 {act_msg:>{hdr_log_msg_width}} "
            f"       1        1          0\n"
        )

        test_log_ver = TestLogVerification(
            log_names=["time_match"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.verify_captured(expected_result=expected_result)

    ####################################################################
    # test_log_verifier_add_call_seq
    ####################################################################
    @pytest.mark.parametrize("simple_str_arg", ("a", "ab", "a1", "xyz123"))
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

        # use deprecated add_msg to verify it still works until we
        # remove it
        log_ver.add_msg(log_msg=log_ver.get_call_seq("alpha"))
        t_logger.debug(f"{simple_str_arg}:{123}")
        log_ver.print_match_results(
            match_results := log_ver.get_match_results(caplog), print_matched=True
        )
        log_ver.verify_match_results(match_results)

        hdr_log_msg = "log_msg"
        hdr_log_msg_width = max(len(hdr_log_msg), (len(simple_str_arg) + 4))

        expected_result = "\n"
        expected_result += "************************************************\n"
        expected_result += "*             log verifier results             *\n"
        expected_result += "************************************************\n"
        expected_result += "Start: Thu Apr 11 2024 19:24:28\n"
        expected_result += "End: Thu Apr 11 2024 19:24:28\n"
        expected_result += "Elapsed time: 0:00:00.006002\n"
        expected_result += "\n"
        expected_result += "************************************************\n"
        expected_result += "*                summary stats                 *\n"
        expected_result += "************************************************\n"
        expected_result += "    type  records  matched  unmatched\n"
        expected_result += "patterns        1        1          0\n"
        expected_result += "log_msgs        1        1          0\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched patterns: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched patterns found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched log_msgs: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched log messages found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "*  matched log_msgs:  *\n"
        expected_result += "***********************\n"
        expected_result += (
            f"log_name  level {hdr_log_msg:>{hdr_log_msg_width}} "
            f" records  matched  unmatched\n"
        )
        expected_result += (
            f"call_seq     10 {simple_str_arg:>{hdr_log_msg_width-4}}:123 "
            f"       1        1          0\n"
        )

        test_log_ver = TestLogVerification(
            log_names=["call_seq"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.verify_captured(expected_result=expected_result)

    ####################################################################
    # test_log_verifier_add_call_seq2
    ####################################################################
    def test_log_verifier_add_call_seq2(
        self,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier add_call_seq method.

        Args:
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
        log_ver.add_pattern(pattern=log_ver.get_call_seq("alpha"))
        my_seq = get_formatted_call_sequence(depth=1)
        t_logger.debug(f"{my_seq}")
        log_ver.print_match_results(
            match_results := log_ver.get_match_results(caplog), print_matched=True
        )
        log_ver.verify_match_results(match_results)

        hdr_log_msg = "log_msg"
        hdr_log_msg_width = max(len(hdr_log_msg), len(my_seq))

        expected_result = "\n"
        expected_result += "************************************************\n"
        expected_result += "*             log verifier results             *\n"
        expected_result += "************************************************\n"
        expected_result += "Start: Thu Apr 11 2024 19:24:28\n"
        expected_result += "End: Thu Apr 11 2024 19:24:28\n"
        expected_result += "Elapsed time: 0:00:00.006002\n"
        expected_result += "\n"
        expected_result += "************************************************\n"
        expected_result += "*                summary stats                 *\n"
        expected_result += "************************************************\n"
        expected_result += "    type  records  matched  unmatched\n"
        expected_result += "patterns        1        1          0\n"
        expected_result += "log_msgs        1        1          0\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched patterns: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched patterns found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched log_msgs: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched log messages found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "*  matched log_msgs:  *\n"
        expected_result += "***********************\n"
        expected_result += (
            f" log_name  level {hdr_log_msg:>{hdr_log_msg_width}} "
            f" records  matched  unmatched\n"
        )
        expected_result += (
            f"call_seq2     10 {my_seq:>{hdr_log_msg_width}} "
            f"       1        1          0\n"
        )

        test_log_ver = TestLogVerification(
            log_names=["call_seq2"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.verify_captured(expected_result=expected_result)

    ####################################################################
    # test_log_verifier_add_call_seq3
    ####################################################################
    @pytest.mark.parametrize("simple_str_arg", ("a", "ab", "a1", "xyz123"))
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
        pattern = (
            f"{esc_thread_str} "
            f"{simple_str_arg} "
            f'{log_ver.get_call_seq(name="alpha")}'
        )
        log_ver.add_pattern(pattern=pattern)

        log_msg = (
            f"{threading.current_thread()} "
            f"{simple_str_arg} "
            f"{get_formatted_call_sequence(depth=1)}"
        )
        t_logger.debug(log_msg)

        log_ver.print_match_results(
            match_results := log_ver.get_match_results(caplog), print_matched=True
        )
        log_ver.verify_match_results(match_results)

        hdr_log_msg = "log_msg"
        hdr_log_msg_width = max(len(hdr_log_msg), len(log_msg))

        expected_result = "\n"
        expected_result += "************************************************\n"
        expected_result += "*             log verifier results             *\n"
        expected_result += "************************************************\n"
        expected_result += "Start: Thu Apr 11 2024 19:24:28\n"
        expected_result += "End: Thu Apr 11 2024 19:24:28\n"
        expected_result += "Elapsed time: 0:00:00.006002\n"
        expected_result += "\n"
        expected_result += "************************************************\n"
        expected_result += "*                summary stats                 *\n"
        expected_result += "************************************************\n"
        expected_result += "    type  records  matched  unmatched\n"
        expected_result += "patterns        1        1          0\n"
        expected_result += "log_msgs        1        1          0\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched patterns: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched patterns found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "* unmatched log_msgs: *\n"
        expected_result += "***********************\n"
        expected_result += "*** no unmatched log messages found ***\n"
        expected_result += "\n"
        expected_result += "***********************\n"
        expected_result += "*  matched log_msgs:  *\n"
        expected_result += "***********************\n"
        expected_result += (
            f" log_name  level {hdr_log_msg:>{hdr_log_msg_width}} "
            f" records  matched  unmatched\n"
        )
        expected_result += (
            f"call_seq3     10 {log_msg:>{hdr_log_msg_width}} "
            f"       1        1          0\n"
        )

        test_log_ver = TestLogVerification(
            log_names=["call_seq3"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        test_log_ver.verify_captured(expected_result=expected_result)

    ####################################################################
    # test_log_verifier_levels
    ####################################################################
    @pytest.mark.parametrize(
        "level_arg",
        (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL),
    )
    def test_log_verifier_levels(
        self,
        level_arg: int,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier with logging disabled and enabled.

        Args:
            level_arg: specifies the log level
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        caplog.clear()

        test_log_ver = TestLogVerification(
            log_names=["diff_levels"],
            capsys_to_use=capsys,
            caplog_to_use=caplog,
            level=level_arg,
        )

        exp_num_unmatched_patterns = 0
        exp_num_unmatched_log_msgs = 0
        exp_num_matched_log_msgs = 0

        for level, msg in [
            (logging.DEBUG, "msg1"),
            (logging.INFO, "msg2"),
            (logging.WARNING, "msg3"),
            (logging.ERROR, "msg4"),
            (logging.CRITICAL, "msg5"),
        ]:
            test_log_ver.issue_log_msg(msg, level=level)
            test_log_ver.add_pattern(pattern=msg, level=level)
            if level_arg <= level:
                exp_num_matched_log_msgs += 1
            else:
                exp_num_unmatched_patterns += 1

        test_log_ver.verify_results(
            print_only=False,
            exp_num_unmatched_patterns=exp_num_unmatched_patterns,
            exp_num_unmatched_log_msgs=exp_num_unmatched_log_msgs,
            exp_num_matched_log_msgs=exp_num_matched_log_msgs,
        )

    ####################################################################
    # test_log_verifier_multi_loggers
    ####################################################################
    @pytest.mark.parametrize("num_log_1_msgs_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_log_2_msgs_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_log_3_msgs_arg", [0, 1, 2])
    @pytest.mark.parametrize("log_1_diff_levels_arg", [True, False])
    @pytest.mark.parametrize("log_2_diff_levels_arg", [True, False])
    @pytest.mark.parametrize("log_3_diff_levels_arg", [True, False])
    def test_log_verifier_multi_loggers(
        self,
        num_log_1_msgs_arg: int,
        num_log_2_msgs_arg: int,
        num_log_3_msgs_arg: int,
        log_1_diff_levels_arg: bool,
        log_2_diff_levels_arg: bool,
        log_3_diff_levels_arg: bool,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier with logging disabled and enabled.

        Args:
            num_log_1_msgs_arg: number of messages for log 1
            num_log_2_msgs_arg: number of messages for log 2
            num_log_3_msgs_arg: number of messages for log 3
            log_1_diff_levels_arg: if True, use different log_levels
            log_2_diff_levels_arg: if True, use different log_levels
            log_3_diff_levels_arg: if True, use different log_levels
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        caplog.clear()

        test_log_ver = TestLogVerification(
            log_names=[
                "multi_log_1",
                "multi_log_2",
                "multi_log_3",
            ],
            capsys_to_use=capsys,
            caplog_to_use=caplog,
        )

        exp_num_unmatched_patterns = 0
        exp_num_unmatched_log_msgs = 0
        exp_num_matched_log_msgs = (
            num_log_1_msgs_arg + num_log_2_msgs_arg + num_log_3_msgs_arg
        )

        idx_to_level: dict[int, int] = {
            0: logging.DEBUG,
            1: logging.INFO,
            2: logging.WARNING,
            3: logging.ERROR,
            4: logging.CRITICAL,
        }

        for idx in range(num_log_1_msgs_arg):
            msg = f"msg{idx}"
            if log_1_diff_levels_arg:
                log_level = idx_to_level[idx]
            else:
                log_level = logging.DEBUG
            test_log_ver.issue_log_msg(msg, level=log_level, log_name="multi_log_1")
            test_log_ver.add_pattern(
                pattern=msg, level=log_level, log_name="multi_log_1"
            )

        for idx in range(num_log_2_msgs_arg):
            msg = f"msg{idx}"
            if log_2_diff_levels_arg:
                log_level = idx_to_level[idx]
            else:
                log_level = logging.DEBUG
            test_log_ver.issue_log_msg(msg, level=log_level, log_name="multi_log_2")
            test_log_ver.add_pattern(
                pattern=msg, level=log_level, log_name="multi_log_2"
            )

        for idx in range(num_log_3_msgs_arg):
            msg = f"msg{idx}"
            if log_3_diff_levels_arg:
                log_level = idx_to_level[idx]
            else:
                log_level = logging.DEBUG
            test_log_ver.issue_log_msg(msg, level=log_level, log_name="multi_log_3")
            test_log_ver.add_pattern(
                pattern=msg, level=log_level, log_name="multi_log_3"
            )

        test_log_ver.verify_results(
            print_only=False,
            print_matched=False,
            exp_num_unmatched_patterns=exp_num_unmatched_patterns,
            exp_num_unmatched_log_msgs=exp_num_unmatched_log_msgs,
            exp_num_matched_log_msgs=exp_num_matched_log_msgs,
        )


########################################################################
# TestLogVerCombos class
########################################################################
@pytest.mark.cover2
class TestLogVerCombos:
    """Test LogVer with various combinations."""

    ####################################################################
    # test_log_verifier_triple_a
    ####################################################################
    @pytest.mark.parametrize("num_a_msg_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_a_pat_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_a_fm_pat_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_aa_msg_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_aa_pat_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_aa_fm_pat_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_aaa_msg_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_aaa_pat_arg", [0, 1, 2])
    @pytest.mark.parametrize("num_aaa_fm_pat_arg", [0, 1, 2])
    def test_log_verifier_triple_a(
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
            log_names=["scratch_1"], capsys_to_use=capsys, caplog_to_use=caplog
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
            print_only=False,
            exp_num_unmatched_patterns=num_exp_accumulator.num_unmatched_patterns,
            exp_num_unmatched_log_msgs=num_exp_accumulator.num_unmatched_log_msgs,
            exp_num_matched_log_msgs=num_exp_accumulator.num_matched_log_msgs,
        )

    ####################################################################
    # test_log_verifier_10m_x_to_y
    ####################################################################
    @pytest.mark.parametrize(
        "num_a_msg_arg",
        [(3000, 0), (3000, 1), (3000, 2), (3000000, 0), (3000000, 1), (3000000, 2)],
    )
    @pytest.mark.parametrize(
        "num_a_pat_arg",
        [
            (0, 0),
            (3000, 0),
            (3000, 1),
            (3000, 2),
            (3000000, 0),
            (3000000, 1),
            (3000000, 2),
        ],
    )
    @pytest.mark.parametrize(
        "num_a_fm_pat_arg",
        [
            (0, 0),
            (3000, 0),
            (3000, 1),
            (3000, 2),
            (3000000, 0),
            (3000000, 1),
            (3000000, 2),
        ],
    )
    # @pytest.mark.parametrize(
    #     "num_a_msg_arg",
    #     [
    #         (30000, 2),
    #     ],
    # )
    # @pytest.mark.parametrize(
    #     "num_a_pat_arg",
    #     [
    #         (0, 0),
    #         # (3000, 0),
    #         # (3000, 1),
    #         # (3000, 2),
    #         # (3000000, 0),
    #         # (3000000, 1),
    #         # (3000000, 2),
    #     ],
    # )
    # @pytest.mark.parametrize(
    #     "num_a_fm_pat_arg",
    #     [
    #         # (0, 0),
    #         # (3000, 0),
    #         # (3000, 1),
    #         # (3000, 2),
    #         # (3000000, 0),
    #         # (3000000, 1),
    #         (30000, 2),
    #     ],
    # )
    def test_log_verifier_10m_x_to_y(
        self,
        num_a_msg_arg: tuple[int, int],
        num_a_pat_arg: tuple[int, int],
        num_a_fm_pat_arg: tuple[int, int],
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier time match.

        Args:
            num_a_msg_arg: number of a log msgs to issue
            num_a_pat_arg: number of a patterns to use
            num_a_fm_pat_arg: number of a fullmatch patterns to use
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        test_log_ver = TestLogVerification(
            log_names=["large_1"], capsys_to_use=capsys, caplog_to_use=caplog
        )
        ################################################################
        # issue log msgs
        ################################################################
        for idx in range(num_a_msg_arg[0]):
            if (num_a_msg_arg[1] == 0) or (num_a_msg_arg[1] == 1 and idx % 2 == 0):
                test_log_ver.issue_log_msg("a")
            else:
                test_log_ver.issue_log_msg(f"a{idx}")

        ################################################################
        # add patterns
        ################################################################
        for idx in range(num_a_pat_arg[0]):
            if (num_a_pat_arg[1] == 0) or (num_a_pat_arg[1] == 1 and idx % 2 == 0):
                test_log_ver.add_pattern("a")
            else:
                test_log_ver.add_pattern(f"a{idx}")

        for idx in range(num_a_fm_pat_arg[0]):
            if (num_a_fm_pat_arg[1] == 0) or (
                num_a_fm_pat_arg[1] == 1 and idx % 2 == 0
            ):
                test_log_ver.add_pattern("a", fullmatch=True)
            else:
                test_log_ver.add_pattern(f"a{idx}", fullmatch=True)

        test_log_ver.verify_results(print_only=True)

    ####################################################################
    # test_log_verifier_10m_x_to_y_diff
    ####################################################################
    @pytest.mark.parametrize("num_a_msg_arg", [0, 100, 10000000])
    @pytest.mark.parametrize("num_a_pat_arg", [0, 100, 10000000])
    @pytest.mark.parametrize("num_a_fm_pat_arg", [0, 100, 10000000])
    def test_log_verifier_10m_x_to_y_diff(
        self,
        num_a_msg_arg: int,
        num_a_pat_arg: int,
        num_a_fm_pat_arg: int,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier time match.

        Args:
            num_a_msg_arg: number of a log msgs to issue
            num_a_pat_arg: number of a patterns to use
            num_a_fm_pat_arg: number of a fullmatch patterns to use
            capsys: pytest fixture to capture print output
            caplog: pytest fixture to capture log output
        """
        test_log_ver = TestLogVerification(
            log_names=["scratch_1"], capsys_to_use=capsys, caplog_to_use=caplog
        )
        ################################################################
        # issue log msgs
        ################################################################
        for idx in range(num_a_msg_arg):
            test_log_ver.issue_log_msg(f"a{idx}")

        ################################################################
        # add patterns
        ################################################################
        for _ in range(num_a_pat_arg):
            test_log_ver.add_pattern("a")

        for _ in range(num_a_fm_pat_arg):
            test_log_ver.add_pattern("a", fullmatch=True)

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

        test_log_ver.verify_results(
            print_only=True,
            exp_num_unmatched_patterns=num_exp_accumulator.num_unmatched_patterns,
            exp_num_unmatched_log_msgs=num_exp_accumulator.num_unmatched_log_msgs,
            exp_num_matched_log_msgs=num_exp_accumulator.num_matched_log_msgs,
        )

    ####################################################################
    # test_log_verifier_combos
    ####################################################################
    @pytest.mark.parametrize("num_exp_msgs1_arg", (0, 1, 2, 3))
    @pytest.mark.parametrize("num_exp_msgs2_arg", (0, 1, 2, 3))
    @pytest.mark.parametrize("num_exp_msgs3_arg", (0, 1, 2, 3))
    @pytest.mark.parametrize("num_act_msgs1_arg", (0, 1, 2, 3))
    @pytest.mark.parametrize("num_act_msgs2_arg", (0, 1, 2, 3))
    @pytest.mark.parametrize("num_act_msgs3_arg", (0, 1, 2, 3))
    def test_log_verifier_combos(
        self,
        num_exp_msgs1_arg: int,
        num_exp_msgs2_arg: int,
        num_exp_msgs3_arg: int,
        num_act_msgs1_arg: int,
        num_act_msgs2_arg: int,
        num_act_msgs3_arg: int,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test log_verifier combos.

        Args:
            num_exp_msgs1_arg: number of expected messages for msg1
            num_exp_msgs2_arg: number of expected messages for msg2
            num_exp_msgs3_arg: number of expected messages for msg3
            num_act_msgs1_arg: number of actual messages for msg1
            num_act_msgs2_arg: number of actual messages for msg2
            num_act_msgs3_arg: number of actual messages for msg3
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
            (num_exp_msgs1_arg, num_act_msgs1_arg, "msg one"),
            (num_exp_msgs2_arg, num_act_msgs2_arg, "msg two"),
            (num_exp_msgs3_arg, num_act_msgs3_arg, "msg three"),
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
                log_ver.add_pattern(pattern=the_msg)

            for _ in range(num_act):
                t_logger.debug(the_msg)

            for _ in range(num_exp_unmatched):
                exp_unmatched_msgs.append(the_msg)

            for _ in range(num_act_unmatched):
                act_unmatched_msgs.append(the_msg)

            for _ in range(num_matched_msgs):
                matched_msgs.append(the_msg)

        log_ver.print_match_results(
            match_results := log_ver.get_match_results(caplog), print_matched=True
        )

        if total_num_exp_unmatched:
            with pytest.raises(UnmatchedPatterns):
                log_ver.verify_match_results(match_results)
        elif total_num_act_unmatched:
            with pytest.raises(UnmatchedLogMessages):
                log_ver.verify_match_results(match_results)
        else:
            log_ver.verify_match_results(match_results)

    ####################################################################
    # test_log_verifier_contention
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
        matched_patterns: list[str] = []

        unmatched_msgs: list[str] = []
        matched_msgs: list[str] = []

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

        test_log_ver = TestLogVerification(
            log_names=["contention_0"], capsys_to_use=capsys, caplog_to_use=caplog
        )

        fullmatch_tf_arg = True
        for pattern in patterns_arg:
            test_log_ver.add_pattern(pattern=pattern, fullmatch=fullmatch_tf_arg)

        for msg in msgs_arg:
            test_log_ver.issue_log_msg(msg)

        test_log_ver.verify_results(
            print_only=False,
            exp_num_unmatched_patterns=len(unmatched_patterns2),
            exp_num_unmatched_log_msgs=len(unmatched_msgs2),
            exp_num_matched_log_msgs=len(matched_msgs2),
        )
