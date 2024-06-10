"""Module log_verifier.

======
LogVer
======

The LogVer class is intended to be used during testing to allow a
pytest test case to verify that the code under test issued log messages
as expected. This is done by providing a collection of regex patterns
that the LogVer will match up to the issued log messages. A report is
printed to the syslog to show any patterns or messages that failed to
match, and optionally the log messages that did match.

:Example1: pytest test case logs a message and verifies

.. code-block:: python

    from scottbrian_utils.log_verifier import LogVer
    import logging
    def test_example1(caplog: pytest.LogCaptureFixture) -> None:
        t_logger = logging.getLogger("example_1")
        log_ver = LogVer(log_name="example_1")
        log_msg = "hello"
        log_ver.add_pattern(pattern=log_msg)
        t_logger.debug(log_msg)
        match_results = log_ver.get_match_results(caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

The output from ``LogVer.print_match_results()`` for test_example1::

        ************************************************
        *             log verifier results             *
        ************************************************
        Start: Thu Apr 11 2024 19:24:28
        End: Thu Apr 11 2024 19:24:28
        Elapsed time: 0:00:00.006002

        ************************************************
        *                summary stats                 *
        ************************************************
            type  records  matched  unmatched
        patterns        1        1          0
        log_msgs        1        1          0

        ***********************
        * unmatched patterns: *
        ***********************
        *** no unmatched patterns found ***

        ***********************
        * unmatched log_msgs: *
        ***********************
        *** no unmatched log messages found ***

        ***********************
        *  matched log_msgs:  *
        ***********************
        log_name  level log_msg records matched unmatched
        example_1    10 hello         1       1         0

:Example2: pytest test case expects two log records, only one is issued

.. code-block:: python

    from scottbrian_utils.log_verifier import LogVer
    import logging

    def test_example2(caplog: pytest.LogCaptureFixture) -> None:
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

The output from ``LogVer.print_match_results()`` for test_example2::

        ************************************************
        *             log verifier results             *
        ************************************************
        Start: Thu Apr 11 2024 19:24:28
        End: Thu Apr 11 2024 19:24:28
        Elapsed time: 0:00:00.006002

        ************************************************
        *                summary stats                 *
        ************************************************
            type  records  matched  unmatched
        patterns        2        1          1
        log_msgs        1        1          0

        ***********************
        * unmatched patterns: *
        ***********************
        log_name  level pattern fullmatch records matched unmatched
        example_2    10 goodbye True            1       0         1

        ***********************
        * unmatched log_msgs: *
        ***********************
        *** no unmatched log messages found ***

        ***********************
        *  matched log_msgs:  *
        ***********************
        log_name  level log_msg records matched unmatched
        example_2    10 hello         1       1         0

:Example3: pytest test case expects one log record, two were issued

.. code-block:: python

    from scottbrian_utils.log_verifier import LogVer
    import logging
    def test_example3(caplog: pytest.LogCaptureFixture) -> None:
        t_logger = logging.getLogger("example_3")
        log_ver = LogVer(log_name="example_3")
        log_msg1 = "hello"
        log_ver.add_pattern(pattern=log_msg1)
        log_msg2 = "goodbye"
        t_logger.debug(log_msg1)
        t_logger.debug(log_msg2)
        log_ver.print_match_results(
            match_results := log_ver.get_match_results(caplog),
            print_matched=True
        )
        with pytest.raises(UnmatchedLogMessages):
            log_ver.verify_match_results(match_results)

The output from ``LogVer.print_match_results()`` for test_example3::

        ************************************************
        *             log verifier results             *
        ************************************************
        Start: Thu Apr 11 2024 19:24:28
        End: Thu Apr 11 2024 19:24:28
        Elapsed time: 0:00:00.006002

        ************************************************
        *                summary stats                 *
        ************************************************
            type  records  matched  unmatched
        patterns        1        1          0
        log_msgs        2        1          1

        ***********************
        * unmatched patterns: *
        ***********************
        *** no unmatched patterns found ***

        ***********************
        * unmatched log_msgs: *
        ***********************
        log_name  level log_msg records matched unmatched
        example_3    10 goodbye       1       0         1

        ***********************
        *  matched log_msgs:  *
        ***********************
        log_name  level log_msg records matched unmatched
        example_3    10 hello         1       1         0

:Example4: pytest test case expect two log records, two were issued,
           one different

.. code-block:: python

    from scottbrian_utils.log_verifier import LogVer
    import logging
    def test_example4(caplog: pytest.LogCaptureFixture) -> None:
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
            match_results := log_ver.get_match_results(caplog),
            print_matched=True
        )
        with pytest.raises(UnmatchedPatterns):
            log_ver.verify_match_results(match_results)

The output from ``LogVer.print_match_results()`` for test_example4::

        ************************************************
        *             log verifier results             *
        ************************************************
        Start: Thu Apr 11 2024 19:24:28
        End: Thu Apr 11 2024 19:24:28
        Elapsed time: 0:00:00.006002

        ************************************************
        *                summary stats                 *
        ************************************************
            type  records  matched  unmatched
        patterns        2        1          1
        log_msgs        2        1          1

        ***********************
        * unmatched patterns: *
        ***********************
        log_name  level pattern fullmatch records matched unmatched
        example_4    10 goodbye True            1       0         1

        ***********************
        * unmatched log_msgs: *
        ***********************
        log_name  level log_msg      records matched unmatched
        example_4    10 see you soon       1       0         1

        ***********************
        *  matched log_msgs:  *
        ***********************
        log_name  level log_msg records matched unmatched
        example_4    10 hello         1       1         0

The log_verifier module contains:

    1) LogVer class with methods:

       a. add_call_seq
       b. get_call_seq
       c. add_pattern
       d. get_match_results
       e. print_match_results
       f. verify_match_results

"""

########################################################################
# Standard Library
########################################################################
from dataclasses import dataclass, field
from datetime import datetime

import logging

import pandas as pd  # type: ignore
import pytest

import re

from typing import Callable, Optional, Type, TYPE_CHECKING, Union
import warnings

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################
from scottbrian_utils.flower_box import print_flower_box_msg

logger = logging.getLogger("log_ver1")
########################################################################
# pandas options
########################################################################
pd.set_option("mode.chained_assignment", "raise")
pd.set_option("display.max_columns", 30)
pd.set_option("max_colwidth", 120)
pd.set_option("display.width", 300)
pd.options.mode.copy_on_write = True

########################################################################
# type aliases
########################################################################
IntFloat = Union[int, float]
OptIntFloat = Optional[IntFloat]


########################################################################
# Msg Exceptions classes
########################################################################
class LogVerError(Exception):
    """Base class for exception in this module."""

    pass


class InvalidLogNameSpecified(LogVerError):
    """Invalid log name was specified during initialization."""

    pass


class InvalidStrColWidthSpecified(LogVerError):
    """Invalid str_col_width was specified during initialization."""

    pass


class UnmatchedExpectedMessages(LogVerError):
    """Unmatched expected messages were found during verify."""

    pass


class UnmatchedActualMessages(LogVerError):
    """Unmatched actual messages were found during verify."""

    pass


class UnmatchedPatterns(LogVerError):
    """Unmatched patterns were found during verify."""

    pass


class UnmatchedLogMessages(LogVerError):
    """Unmatched log messages were found during verify."""

    pass


@dataclass
class MatchResults:
    """Match results returned by get_match_results method."""

    num_patterns: int = 0
    num_matched_patterns: int = 0
    num_unmatched_patterns: int = 0
    num_log_msgs: int = 0
    num_matched_log_msgs: int = 0
    num_unmatched_log_msgs: int = 0
    pattern_grp: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    log_msg_grp: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())


@dataclass
class PotentialMatch:
    count: int = 0
    item: str = ""


########################################################################
# LogVer class
########################################################################
class LogVer:
    """Log Message Verification Class."""

    ####################################################################
    # __init__
    ####################################################################
    def __init__(
        self, log_name: str = "root", str_col_width: Optional[int] = None
    ) -> None:
        """Initialize a LogVer object.

        Args:
            log_name: name of the logger
            str_col_width: If specifief, limits the maximum width for
                string values in the display produced by method
                print_match_results. The string values that are limited
                are for columns *log_name*, *log_msg*, *pattern*, and
                *fullmatch*. The specified limit must be an int with a
                value of 9 or greater.

        Example: create a logger and a LogVer instance
        >>> logger = logging.getLogger('example_logger')
        >>> log_ver = LogVer('example_logger')

        """
        self.specified_args = locals()  # used for __repr__, see below

        self.start_DT = datetime.now()
        self.end_DT = datetime.now()

        if isinstance(log_name, str):
            self.log_name = log_name
        else:
            raise InvalidLogNameSpecified(
                f"The specified log_name of {log_name} is invalid - it must be of "
                f"type str."
            )

        self.logger = logging.getLogger(log_name)

        if str_col_width is None or (
            isinstance(str_col_width, int) and 9 <= str_col_width
        ):
            self.str_col_width = str_col_width
        else:
            raise InvalidStrColWidthSpecified(
                f"The specified str_col_width of {str_col_width} is invalid - it must "
                f"be an int value greater than or equal to 9."
            )

        self.call_seqs: dict[str, str] = {}
        self.patterns: list[
            tuple[
                str,
                int,
                str,
                bool,
            ]
        ] = []

    ####################################################################
    # __repr__
    ####################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        """
        if TYPE_CHECKING:
            __class__: Type[LogVer]  # noqa: F842
        classname = self.__class__.__name__
        parms = ""
        comma = ""

        for key, item in self.specified_args.items():
            if item:  # if not None
                if key in ("log_name",):
                    sq = ""
                    if type(item) is str:
                        sq = "'"
                    parms += comma + f"{key}={sq}{item}{sq}"
                    comma = ", "  # after first item, now need comma

        return f"{classname}({parms})"

    ####################################################################
    # add_call_seq
    ####################################################################
    def add_call_seq(self, name: str, seq: str) -> None:
        """Add a call sequence for a given name.

        Args:
            name: name for whom the call sequence represents
            seq: the call sequence in a format as described by
                   get_formatted_call_sequence in diag_msg.py
                   from the scottbrian_utils package

        """
        self.call_seqs[name] = seq + ":[0-9]*"

    ####################################################################
    # add_call_seq
    ####################################################################
    def get_call_seq(self, name: str) -> str:
        """Retrieve a call sequence by name.

        Args:
            name: name for whom the call sequence represents

        Returns:
            the call sequence in a format as described by
              get_formatted_call_sequence in diag_msg.py with the regex
              string ":[0-9]*" appended to represent the source line
              number to match

        """
        return self.call_seqs[name]

    ####################################################################
    # add_msg
    ####################################################################
    def add_msg(
        self,
        log_msg: str,
        log_level: int = logging.DEBUG,
        log_name: Optional[str] = None,
        fullmatch: bool = False,
    ) -> None:
        """Add a message to the expected log messages.

        Args:
            log_msg: expected message to add
            log_level: expected logging level
            log_name: expected logger name
            fullmatch: if True, use regex fullmatch instead of
                match in method get_match_results

        .. deprecated:: 3.0.0
           Use method :func:`add_pattern()` instead.

        """
        warnings.warn(
            message="LogVer.add_msg() is deprecated as of version 3.0.0 and will be "
            "removed in a future release. Use LogVer.add_pattern() instead",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.add_pattern(
            pattern=log_msg,
            level=log_level,
            log_name=log_name,
            fullmatch=fullmatch,
        )

    ####################################################################
    # add_pattern
    ####################################################################
    def add_pattern(
        self,
        pattern: str,
        level: int = logging.DEBUG,
        log_name: Optional[str] = None,
        fullmatch: bool = True,
    ) -> None:
        """Add a pattern to be matched to a log message.

        Args:
            pattern: pattern to use to find log_msg in the log
            level: logging level to use
            log_name: logger name to use
            fullmatch: if True, use regex fullmatch in method
                get_match_results, otherwise use regex match

        .. versionadded:: 3.0.0
           Method :func:`add_pattern` replaces method :func:`add_msg`.

        Example: add two patterns, each at a different level

        .. code-block:: python

            def test_example(caplog: pytest.LogCaptureFixture) -> None:
                t_logger = logging.getLogger("example_5")
                log_ver = LogVer("example_5")
                log_msg1 = "hello"
                log_msg2 = "goodbye"
                log_ver.add_pattern(pattern=log_msg1)
                log_ver.add_pattern(pattern=log_msg2,
                                    level=logging.ERROR)
                t_logger.debug(log_msg1)
                t_logger.error(log_msg2)
                match_results = log_ver.get_match_results(caplog=caplog)
                log_ver.print_match_results(match_results,
                                            print_matched=True)
                log_ver.verify_match_results(match_results)

        The output from ``LogVer.print_match_results()`` for
        test_example::

            ************************************************
            *             log verifier results             *
            ************************************************
            Start: Thu Apr 11 2024 19:24:28
            End: Thu Apr 11 2024 19:24:28
            Elapsed time: 0:00:00.006002

            ************************************************
            *                summary stats                 *
            ************************************************
                type  records  matched  unmatched
            patterns        2        2          0
            log_msgs        2        2          0

            ***********************
            * unmatched patterns: *
            ***********************
            *** no unmatched patterns found ***

            ***********************
            * unmatched log_msgs: *
            ***********************
            *** no unmatched log messages found ***

            ***********************
            *  matched log_msgs:  *
            ***********************
            log_name  level log_msg records matched unmatched
            example_5    10 hello         1       1         0
            example_5    40 goodbye       1       1         0

        """
        if log_name:
            log_name_to_use = log_name
        else:
            log_name_to_use = self.log_name

        if fullmatch:
            self.patterns.append(
                (
                    log_name_to_use,
                    level,
                    pattern,
                    True,
                )
            )
        else:
            self.patterns.append(
                (
                    log_name_to_use,
                    level,
                    pattern,
                    False,
                )
            )

    ####################################################################
    # msg
    ####################################################################
    def test_msg(
        self,
        log_msg: str,
        level: int = logging.DEBUG,
        stacklevel: int = 2,
        enabled: Union[bool, Callable[..., bool]] = True,
    ) -> None:
        """Issue a log msg and add its pattern.

        Args:
            log_msg: log message to issue
            level: logging level to use
            stacklevel: stacklevel to use on the call to logger
            enabled: If True, allow the log message to be logged

        Notes:

            1) This method makes it easier to issue a log message in a
               test case by also adding the pattern.

        .. versionadded:: 3.0.0

        Example: issue a test msg

        .. code-block:: python

            def test_example(caplog: pytest.LogCaptureFixture) -> None:
                log_ver = LogVer("example_6")
                log_ver.test_msg("my test message")

                match_results = log_ver.get_match_results(caplog=caplog)
                log_ver.print_match_results(match_results,
                                            print_matched=True)
                log_ver.verify_match_results(match_results)

        The output from ``LogVer.print_match_results()`` for
        test_example::

            ************************************************
            *             log verifier results             *
            ************************************************
            Start: Thu Apr 11 2024 19:24:28
            End: Thu Apr 11 2024 19:24:28
            Elapsed time: 0:00:00.006002

            ************************************************
            *                summary stats                 *
            ************************************************
                type  records  matched  unmatched
            patterns        1        1          0
            log_msgs        1        1          0

            ***********************
            * unmatched patterns: *
            ***********************
            *** no unmatched patterns found ***

            ***********************
            * unmatched log_msgs: *
            ***********************
            *** no unmatched log messages found ***

            ***********************
            *  matched log_msgs:  *
            ***********************
            log_name  level log_msg     records matched unmatched
            example_6    10 my test msg       1       1         0


        """
        if (type(enabled) is bool and enabled) or (callable(enabled) and enabled()):
            self.add_pattern(pattern=re.escape(log_msg), level=level)
            self.logger.log(level=level, msg=log_msg, stacklevel=stacklevel)

    ####################################################################
    # get_match_results
    ####################################################################
    def get_match_results(self, caplog: pytest.LogCaptureFixture) -> MatchResults:
        """Match the patterns to log records.

        Args:
            caplog: pytest fixture that captures log messages

        Returns:
            MatchResults object, which contain the results of the
            matching operation. This will include a summary for the
            patterns and messages, and the data frames containing the
            patterns and messaged used to print and verify the results.

        """
        self.start_DT = datetime.now()

        msg_df = pd.DataFrame(
            caplog.record_tuples,
            columns=("log_name", "level", "log_msg"),
        )

        msg_grp = msg_df.groupby(msg_df.columns.tolist(), as_index=False).size()
        msg_grp.rename(columns={"size": "records"}, inplace=True)

        work_msg_grp = msg_grp.copy()

        work_msg_grp["potential_matches"] = [set() for _ in range(len(work_msg_grp))]
        work_msg_grp["num_potential_matches"] = 0
        work_msg_grp.rename(columns={"records": "num_avail"}, inplace=True)

        msg_grp["matched"] = 0

        pattern_df = pd.DataFrame(
            self.patterns,
            columns=("log_name", "level", "pattern", "fullmatch"),
        )

        pattern_grp = pattern_df.groupby(
            pattern_df.columns.tolist(), as_index=False
        ).size()
        pattern_grp.rename(columns={"size": "records"}, inplace=True)

        work_pattern_grp = pattern_grp.copy()

        work_pattern_grp["potential_matches"] = [
            set() for _ in range(len(work_pattern_grp))
        ]
        work_pattern_grp["num_potential_matches"] = 0
        work_pattern_grp.rename(columns={"records": "num_avail"}, inplace=True)

        pattern_grp["matched"] = 0

        ################################################################
        # set potential matches in both data frames
        ################################################################
        for p_row in work_pattern_grp.itertuples():
            # pattern_potentials = []
            pattern_potentials = set()
            if p_row.fullmatch:
                match_grp = work_msg_grp[
                    (work_msg_grp["log_msg"].str.fullmatch(p_row.pattern))
                    & (work_msg_grp["log_name"] == p_row.log_name)
                    & (work_msg_grp["level"] == p_row.level)
                ]
            else:
                match_grp = work_msg_grp[
                    (work_msg_grp["log_msg"].str.match(p_row.pattern))
                    & (work_msg_grp["log_name"] == p_row.log_name)
                    & (work_msg_grp["level"] == p_row.level)
                ]

            if len(match_grp) == 1:
                msg_idx = match_grp.index[0]
                num_matched = min(
                    p_row.num_avail, work_msg_grp.at[msg_idx, "num_avail"]
                )
                work_msg_grp.at[msg_idx, "num_avail"] -= num_matched
                msg_grp.at[msg_idx, "matched"] += num_matched

                pattern_grp.at[p_row.Index, "matched"] += num_matched
                # no need to update num_avail for work_pattern_grp - the
                # entry will get filtered out later in the main loop
                # because num_potential_matches will be zero
                continue

            if len(match_grp) == 0:
                # no need to update work_pattern_grp - the
                # entry will get filtered out later in the main loop
                # because num_potential_matches will be zero
                continue

            for m_row in match_grp.itertuples():
                pattern_potentials |= {m_row.Index}
                work_msg_grp.at[m_row.Index, "potential_matches"] |= {p_row.Index}
                work_msg_grp.at[m_row.Index, "num_potential_matches"] += 1

            work_pattern_grp.at[p_row.Index, "potential_matches"] = pattern_potentials
            work_pattern_grp.at[p_row.Index, "num_potential_matches"] = len(
                pattern_potentials
            )

        ################################################################
        # settle matches
        ################################################################
        while True:
            work_pattern_grp = work_pattern_grp[
                work_pattern_grp["num_potential_matches"] > 0
            ]
            if work_pattern_grp.empty:
                break

            work_msg_grp = work_msg_grp[work_msg_grp["num_potential_matches"] > 0]
            # the work_pattern_grp being non-empty implies that
            # work_msg_grp will also be non-empty

            p_min_potential_matches = work_pattern_grp["num_potential_matches"].min()
            m_min_potential_matches = work_msg_grp["num_potential_matches"].min()

            if p_min_potential_matches <= m_min_potential_matches:
                self.search_df(
                    avail_df=work_pattern_grp,
                    search_arg_df=pattern_grp,
                    search_targ_df=msg_grp,
                    targ_work_grp=work_msg_grp,
                    min_potential_matches=p_min_potential_matches,
                )
            else:
                self.search_df(
                    avail_df=work_msg_grp,
                    search_arg_df=msg_grp,
                    search_targ_df=pattern_grp,
                    targ_work_grp=work_pattern_grp,
                    min_potential_matches=m_min_potential_matches,
                )

        ################################################################
        # reconcile pattern matches
        ################################################################
        num_patterns = pattern_grp["records"].sum()
        num_matched_patterns = pattern_grp.matched.sum()
        num_unmatched_patterns = num_patterns - num_matched_patterns
        pattern_grp["unmatched"] = pattern_grp["records"] - pattern_grp["matched"]

        ################################################################
        # reconcile msg matches
        ################################################################
        num_msgs = msg_grp["records"].sum()
        num_matched_msgs = msg_grp.matched.sum()
        num_unmatched_msgs = num_msgs - num_matched_msgs
        msg_grp["unmatched"] = msg_grp["records"] - msg_grp["matched"]

        self.end_DT = datetime.now()
        return MatchResults(
            num_patterns=num_patterns,
            num_matched_patterns=num_matched_patterns,
            num_unmatched_patterns=num_unmatched_patterns,
            num_log_msgs=num_msgs,
            num_matched_log_msgs=num_matched_msgs,
            num_unmatched_log_msgs=num_unmatched_msgs,
            pattern_grp=pattern_grp,
            log_msg_grp=msg_grp,
        )

    ####################################################################
    # search_df for matches
    ####################################################################
    @staticmethod
    def search_df(
        avail_df: pd.DataFrame,
        search_arg_df: pd.DataFrame,
        search_targ_df: pd.DataFrame,
        targ_work_grp: pd.DataFrame,
        min_potential_matches: int,
    ) -> None:
        """Search the data frames for matches.

        Args:
            avail_df: data frame of available entries
            search_arg_df: data frame that has the search arg
            search_targ_df: data frame that has the search target
            targ_work_grp: work group dataframe that has the
                target avail count
            min_potential_matches: the currently known minimum number of
                non-zero potential matches that need to be processed

        """
        # This method is called to choose the best pairing of potential
        # matches between the pattern and log messages.
        # We iterate ove the search_arg_df, selecting only entries whose
        # number of potential_matches is equal to min_potential_matches.
        # The idea is to make sure we give entries with few choices a
        # chance to claim matches before entries with more choices
        # claim them.
        # Once we make a claim, we remove the choice from all entries,
        # which now means some entries may now have fewer choices than
        # min_potential_matches. In order to avoid these entries from
        # facing that same scenario of having their limited choices
        # "stolen" by an entry with more choices, we need to reduce
        # min_potential_matches dynamically.
        # We stop calling when we determine no additional matches are
        # possible as indicated when all entries have either made a
        # match are have exhausted their potential_matches.

        def adjust_potential_matches(
            adj_df: pd.DataFrame,
            idx_adjust_list: list[int],
            remove_idx: int,
            min_len: int,
        ) -> int:
            """Adjust the potential_matches list for the adj_df

            Args:
                adj_df: data frame whose potential_matches need to be
                    adjusted
                idx_adjust_list: list of idxs to remove from the
                    potential_matches list
                remove_idx: idx to remove from the potential_matches
                    list
                min_len: min_potential_matches

            Returns:
                length of adjusted potential_matches list

            """
            ret_min_len = min_len
            for idx_adjust in idx_adjust_list:
                if remove_idx in adj_df.at[idx_adjust, "potential_matches"]:
                    adj_df.at[idx_adjust, "potential_matches"] -= {remove_idx}
                    adj_df.at[idx_adjust, "num_potential_matches"] -= 1
                    new_len = adj_df.at[idx_adjust, "num_potential_matches"]
                    ret_min_len = min(ret_min_len, new_len)  # could be zero

            return ret_min_len

        min_arg_potential_matches = min_potential_matches
        min_targ_potential_matches = min_potential_matches

        for search_item in avail_df.itertuples():
            if search_item.num_potential_matches == min_potential_matches:
                arg_num_avail = search_item.num_avail
                target_adj_potential_matches = search_item.potential_matches.copy()
                for potential_idx in search_item.potential_matches:
                    num_matched = min(
                        arg_num_avail, targ_work_grp.at[potential_idx, "num_avail"]
                    )

                    search_arg_df.at[search_item.Index, "matched"] += num_matched

                    arg_num_avail -= num_matched

                    search_targ_df.at[potential_idx, "matched"] += num_matched
                    targ_work_grp.at[potential_idx, "num_avail"] -= num_matched

                    target_adj_potential_matches -= {potential_idx}
                    if targ_work_grp.at[potential_idx, "num_avail"] != 0:
                        targ_work_grp.at[potential_idx, "potential_matches"] -= {
                            search_item.Index
                        }
                        targ_work_grp.at[potential_idx, "num_potential_matches"] -= 1
                        min_targ_potential_matches = min(
                            min_targ_potential_matches,
                            targ_work_grp.at[potential_idx, "num_potential_matches"],
                        )
                    else:
                        arg_df_idx_adjust_list = targ_work_grp.at[
                            potential_idx, "potential_matches"
                        ].copy()

                        # clear list - we have no more avail
                        targ_work_grp.at[potential_idx, "potential_matches"] = set()
                        targ_work_grp.at[potential_idx, "num_potential_matches"] = 0

                        # no need to adjust the arg list since we
                        # will remove the entire list below
                        arg_df_idx_adjust_list -= {search_item.Index}

                        if arg_df_idx_adjust_list:
                            new_arg_min = adjust_potential_matches(
                                adj_df=avail_df,
                                idx_adjust_list=arg_df_idx_adjust_list,
                                remove_idx=potential_idx,
                                min_len=min_potential_matches,
                            )
                            min_arg_potential_matches = min(
                                min_arg_potential_matches, new_arg_min
                            )
                    if arg_num_avail == 0:
                        break

                # We are done with this search_arg - we found zero or
                # more targets and set whatever matches we could.
                # Remove the potential list, set the num_avail to zero,
                # and tell all potential targets to remove this arg
                # from their potential lists
                avail_df.at[search_item.Index, "potential_matches"] = set()
                avail_df.at[search_item.Index, "num_potential_matches"] = 0

                if target_adj_potential_matches:
                    new_targ_min = adjust_potential_matches(
                        adj_df=targ_work_grp,
                        idx_adjust_list=target_adj_potential_matches,
                        remove_idx=search_item.Index,
                        min_len=min_potential_matches,
                    )
                    min_targ_potential_matches = min(
                        min_targ_potential_matches, new_targ_min
                    )

                if min_targ_potential_matches < min_arg_potential_matches:
                    return

                min_potential_matches = min_arg_potential_matches

        return

    ####################################################################
    # print_match_results
    ####################################################################
    # @staticmethod
    def print_match_results(
        self, match_results: MatchResults, print_matched: bool = False
    ) -> None:
        """Print the match results.

        Args:
            match_results: contains the results to be printed
            print_matched: if True, print the matched records, otherwise
                skip printing the matched records

        .. versionchanged:: 3.0.0
           *print_matched* keyword default changed to False

        """
        ################################################################
        # print report header
        ################################################################
        print_flower_box_msg("            log verifier results            ")
        print(f"Start: {self.start_DT.strftime('%a %b %d %Y %H:%M:%S')}")
        print(f"End: {self.end_DT.strftime('%a %b %d %Y %H:%M:%S')}")
        print(f"Elapsed time: {self.end_DT - self.start_DT}")

        ################################################################
        # print summary stats
        ################################################################
        summary_stats_df = pd.DataFrame(
            {
                "type": ["patterns", "log_msgs"],
                "records": [
                    match_results.num_patterns,
                    match_results.num_log_msgs,
                ],
                "matched": [
                    match_results.num_matched_patterns,
                    match_results.num_matched_log_msgs,
                ],
                "unmatched": [
                    match_results.num_unmatched_patterns,
                    match_results.num_unmatched_log_msgs,
                ],
            }
        )

        print_flower_box_msg("               summary stats                ")
        print_stats = summary_stats_df.to_string(
            columns=[
                "type",
                "records",
                "matched",
                "unmatched",
            ],
            index=False,
        )

        print(print_stats)

        ################################################################
        # print unmatched patterns
        ################################################################
        print_flower_box_msg("unmatched patterns:")

        unmatched_pattern_df = match_results.pattern_grp[
            match_results.pattern_grp.records != match_results.pattern_grp.matched
        ]
        if unmatched_pattern_df.empty:
            print("*** no unmatched patterns found ***")
        else:
            self.print_df(
                df_to_print=unmatched_pattern_df,
                col_names=[
                    "log_name",
                    "level",
                    "pattern",
                    "fullmatch",
                    "records",
                    "matched",
                    "unmatched",
                ],
                left_justify_col_names=[
                    "log_name",
                    "pattern",
                    "fullmatch",
                ],
            )

        ################################################################
        # print unmatched log messages
        ################################################################
        print_flower_box_msg("unmatched log_msgs:")

        unmatched_msg_df = match_results.log_msg_grp[
            match_results.log_msg_grp.records != match_results.log_msg_grp.matched
        ]

        if unmatched_msg_df.empty:
            print("*** no unmatched log messages found ***")
        else:
            self.print_df(
                df_to_print=unmatched_msg_df,
                col_names=[
                    "log_name",
                    "level",
                    "log_msg",
                    "records",
                    "matched",
                    "unmatched",
                ],
                left_justify_col_names=[
                    "log_name",
                    "log_msg",
                ],
            )

        ################################################################
        # print matched log messages
        ################################################################
        if print_matched:
            print_flower_box_msg(" matched log_msgs: ")
            matched_msg_df = match_results.log_msg_grp[
                match_results.log_msg_grp.records == match_results.log_msg_grp.matched
            ]

            if matched_msg_df.empty:
                print("*** no matched log messages found ***")
            else:
                self.print_df(
                    df_to_print=matched_msg_df,
                    col_names=[
                        "log_name",
                        "level",
                        "log_msg",
                        "records",
                        "matched",
                        "unmatched",
                    ],
                    left_justify_col_names=[
                        "log_name",
                        "log_msg",
                    ],
                )

    ####################################################################
    # print_df
    ####################################################################
    def print_df(
        self,
        df_to_print: pd.DataFrame,
        col_names: list[str],
        left_justify_col_names: list[str],
    ) -> None:
        """Prin the data set to screen.

        Args:
            df_to_print: the dataframe to print
            col_names: list of column names to be printed
            left_justify_col_names: list of column names to be printed
                left justified

        """

        ################################################################
        # get_left_justify_rtn
        ################################################################
        def get_left_justify_rtn(val_str_len: int) -> Callable[[str | bool], str]:
            def left_justify(value: str | bool) -> str:
                if len(str(value)) > val_str_len:
                    ret_str = str(value)[:val_str_len]
                else:
                    ret_str = str(value)
                return f"{ret_str:<{val_str_len}}"

            return left_justify

        formatters: dict[str, Callable[[str | bool], str]] = {}
        header: list[str] = []

        # we build a dictionary of functions keyed by column names that
        for col_name in col_names:
            if col_name in left_justify_col_names:
                maxlen = max(
                    df_to_print[col_name].astype(str).str.len().max(), len(col_name)
                )
                if self.str_col_width is not None:
                    maxlen = min(maxlen, self.str_col_width)
                formatters[col_name] = get_left_justify_rtn(maxlen)
                header.append(col_name.ljust(maxlen))
            else:
                header.append(col_name)

        df_print_str = df_to_print.to_string(
            formatters=formatters,
            columns=col_names,
            header=header,
            index=False,
        )
        print(df_print_str)

    ####################################################################
    # verify log messages
    ####################################################################
    @staticmethod
    def verify_log_results(match_results: MatchResults) -> None:
        """Verify that each log message issued is as expected.

        Args:
            match_results: contains the results to be verified

        .. deprecated:: 3.0.0
           Use method :func:`verify_match_results` instead.

        Raises:
            UnmatchedExpectedMessages: There are expected log messages
                that failed to match actual log messages.
            UnmatchedActualMessages: There are actual log messages that
                failed to match expected log messages.



        """
        warnings.warn(
            message="LogVer.verify_log_results() is deprecated as of"
            " version 3.0.0 and will be removed in a future release. "
            "Use LogVer.verify_match_results() instead",
            category=DeprecationWarning,
            stacklevel=2,
        )
        if match_results.num_unmatched_patterns:
            raise UnmatchedExpectedMessages(
                f"There are {match_results.num_unmatched_patterns} "
                "expected log messages that failed to match actual log "
                "messages."
            )

        if match_results.num_unmatched_log_msgs:
            raise UnmatchedActualMessages(
                f"There are {match_results.num_unmatched_log_msgs} "
                "actual log messages that failed to match expected log "
                "messages."
            )

    ####################################################################
    # verify_match_results
    ####################################################################
    @staticmethod
    def verify_match_results(match_results: MatchResults) -> None:
        """Verify that each log message issued is as expected.

        Args:
            match_results: contains the results to be verified

        Raises:
            UnmatchedPatterns: One or more patterns failed to match
                their intended log messages. The patterns and/or the
                log messages may have been incorrectly specified.
            UnmatchedLogMessages: One or more log messages failed to be
                matched by corresponding patterns. The patterns and/or
                the log messages may have been incorrectly specified.

        """
        if match_results.num_unmatched_patterns:
            if match_results.num_unmatched_patterns == 1:
                is_are = "is"
                pattern_s = "pattern"
            else:
                is_are = "are"
                pattern_s = "patterns"

            raise UnmatchedPatterns(
                f"There {is_are} {match_results.num_unmatched_patterns} {pattern_s} "
                f"that did not match any log messages."
            )

        if match_results.num_unmatched_log_msgs:
            if match_results.num_unmatched_log_msgs == 1:
                is_are = "is"
                log_msg_s = "log messages"
            else:
                is_are = "are"
                log_msg_s = "log messages"
            raise UnmatchedLogMessages(
                f"There {is_are} {match_results.num_unmatched_log_msgs} {log_msg_s} "
                f"that did not get matched by any patterns."
            )
