"""Module log_verifier.

======
LogVer
======

The LogVer class is intended to be used during testing to allow a
test case to specify expected log messages and then verify that they
have been issued.

:Example1: pytest test case logs a message and verifies

.. code-block:: python

    from scottbrian_utils.log_verifier import LogVer
    import logging
    def test_example1(caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger('example_1')
        log_ver = LogVer('example_1')
        log_msg = 'hello'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

The output from ``LogVer.print_match_results()`` for test_example1::

    **********************************
    * number expected log records: 1 *
    * number expected unmatched  : 0 *
    * number actual log records  : 1 *
    * number actual unmatched    : 0 *
    * number of matched records  : 1 *
    **********************************

    *********************************
    * unmatched expected records    *
    * (logger name, level, message) *
    *********************************

    *********************************
    * unmatched actual records      *
    * (logger name, level, message) *
    *********************************

    *********************************
    * matched records               *
    * (logger name, level, message) *
    *********************************
    ('example_1', 10, 'hello')

:Example2: pytest test case expects two log records, only one was issued

.. code-block:: python

    from scottbrian_utils.log_verifier import LogVer
    import logging
    def test_example2(caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger('example_2')
        log_ver = LogVer('example_2')
        log_msg1 = 'hello'
        log_ver.add_msg(log_msg=log_msg1)
        log_msg2 = 'goodbye'
        log_ver.add_msg(log_msg=log_msg2)
        logger.debug(log_msg1)
        log_ver.get_match_results()
        log_ver.print_match_results()

The output from ``LogVer.print_match_results()`` for test_example2::

    **********************************
    * number expected log records: 2 *
    * number expected unmatched  : 1 *
    * number actual log records  : 1 *
    * number actual unmatched    : 0 *
    * number of matched records  : 1 *
    **********************************

    *********************************
    * unmatched expected records    *
    * (logger name, level, message) *
    *********************************
    ('example_2', 10, 'goodbye')

    *********************************
    * unmatched actual records      *
    * (logger name, level, message) *
    *********************************

    *********************************
    * matched records               *
    * (logger name, level, message) *
    *********************************
    ('example_2', 10, 'hello')

:Example3: pytest test case expects one log record, two were issued

.. code-block:: python

    from scottbrian_utils.log_verifier import LogVer
    import logging
    def test_example3(caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger('example_3')
        log_ver = LogVer('example_3')
        log_msg1 = 'hello'
        log_ver.add_msg(log_msg=log_msg1)
        log_msg2 = 'goodbye'
        logger.debug(log_msg1)
        logger.debug(log_msg2)
        log_ver.get_match_results()
        log_ver.print_match_results()

The output from ``LogVer.print_match_results()`` for test_example3::

    **********************************
    * number expected log records: 1 *
    * number expected unmatched  : 0 *
    * number actual log records  : 2 *
    * number actual unmatched    : 1 *
    * number of matched records  : 1 *
    **********************************

    *********************************
    * unmatched expected records    *
    * (logger name, level, message) *
    *********************************

    *********************************
    * unmatched actual records      *
    * (logger name, level, message) *
    *********************************
    ('example_3', 10, 'goodbye')

    *********************************
    * matched records               *
    * (logger name, level, message) *
    *********************************
    ('example_3', 10, 'hello')

:Example4: pytest test case expect two log records, two were issued,
           one different

.. code-block:: python

    from scottbrian_utils.log_verifier import LogVer
    import logging
    def test_example4(caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger('example_4')
        log_ver = LogVer('example_4')
        log_msg1 = 'hello'
        log_ver.add_msg(log_msg=log_msg1)
        log_msg2a = 'goodbye'
        log_ver.add_msg(log_msg=log_msg2a)
        log_msg2b = 'see you soon'
        logger.debug(log_msg1)
        logger.debug(log_msg2b)
        log_ver.get_match_results()
        log_ver.print_match_results()

The output from ``LogVer.print_match_results()`` for test_example4::

    **********************************
    * number expected log records: 2 *
    * number expected unmatched  : 1 *
    * number actual log records  : 2 *
    * number actual unmatched    : 1 *
    * number of matched records  : 1 *
    **********************************

    *********************************
    * unmatched expected records    *
    * (logger name, level, message) *
    *********************************
    ('example_4', 10, 'goodbye')

    *********************************
    * unmatched actual records      *
    * (logger name, level, message) *
    *********************************
    ('example_4', 10, 'see you soon')

    *********************************
    * matched records               *
    * (logger name, level, message) *
    *********************************
    ('example_4', 10, 'hello')

The log_verifier module contains:

    1) LogVer class with methods:

       a. add_call_seq
       b. get_call_seq
       c. add_msg
       d. get_match_results
       e. print_match_results
       f. verify_log_results

"""

########################################################################
# Standard Library
########################################################################
# from collections import defaultdict
from dataclasses import dataclass

# import itertools as it
import logging

# import more_itertools as mi
import pandas as pd
import pyarrow as pa
import pytest
import re
from typing import Optional, Type, TYPE_CHECKING, Union
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
    unmatched_patterns: str = ""
    unmatched_log_msgs: str = ""
    matched_log_msgs: str = ""


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
    def __init__(self, log_name: str = "root") -> None:
        """Initialize a LogVer object.

        Args:
            log_name: name of the logger

        Example: create a logger and a LogVer instance
        >>> logger = logging.getLogger('example_logger')
        >>> log_ver = LogVer('example_logger')

        """
        self.specified_args = locals()  # used for __repr__, see below
        self.call_seqs: dict[str, str] = {}
        self.patterns: list[
            tuple[
                str,
                int,
                str,
                bool,
            ]
        ] = []
        self.log_name = log_name

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
            log_level=log_level,
            log_name=log_name,
            fullmatch=fullmatch,
        )

    ####################################################################
    # add_pattern
    ####################################################################
    def add_pattern(
        self,
        pattern: str,
        log_level: int = logging.DEBUG,
        log_name: Optional[str] = None,
        fullmatch: bool = False,
    ) -> None:
        """Add a pattern to be matched to a log message.

        Args:
            pattern: pattern to use to find log_msg in the log
            log_level: logging level to use
            log_name: logger name to use
            fullmatch: if True, use regex fullmatch instead of
                match in method get_match_results

        .. versionadded:: 3.0.0
           Method :func:`add_pattern` replaces method :func:`add_msg`.

        Example: add two patterns, each at a different level

        .. code-block:: python

            def test_example(caplog: pytest.LogCaptureFixture
                            ) -> None:
                logger = logging.getLogger('add_msg')
                log_ver = LogVer('add_msg')
                log_msg1 = 'hello'
                log_msg2 = 'goodbye'
                log_ver.add_pattern(pattern=log_msg1)
                log_ver.add_pattern(pattern=log_msg2,
                                    log_level=logging.ERROR)
                logger.debug(log_msg1)
                logger.error(log_msg2)
                match_results = log_ver.get_match_results()
                log_ver.print_match_results(match_results)
                log_ver.verify_log_results(match_results)

        The output from ``LogVer.print_match_results()`` for
        test_example::

            **********************************
            * number expected log records: 2 *
            * number expected unmatched  : 1 *
            * number actual log records  : 1 *
            * number actual unmatched    : 0 *
            * number of matched records  : 1 *
            **********************************

            *********************************
            * unmatched expected records    *
            * (logger name, level, message) *
            *********************************

            *********************************
            * unmatched actual records      *
            * (logger name, level, message) *
            *********************************

            *********************************
            * matched records               *
            * (logger name, level, message) *
            *********************************
            ('add_msg', 10, 'hello')
            ('add_msg', 40, 'goodbye')

        """
        if log_name:
            log_name_to_use = log_name
        else:
            log_name_to_use = self.log_name

        if fullmatch:
            self.patterns.append(
                (
                    log_name_to_use,
                    log_level,
                    pattern,
                    True,
                )
            )
        else:
            self.patterns.append(
                (
                    log_name_to_use,
                    log_level,
                    pattern,
                    False,
                )
            )

    ####################################################################
    # get_match_results
    ####################################################################
    def get_match_results(self, caplog: pytest.LogCaptureFixture) -> MatchResults:
        """Match the expected to actual log records.

        Args:
            caplog: pytest fixture that captures log messages

        Returns:
            Number of expected records, number of actual records,
              number of matching records, list of unmatched expected
              records, list of unmatched actual records, and list
              or matching records

        """
        pattern_col_names = (
            "log_name",
            "log_level",
            "pattern",
            "fullmatch",
        )
        pattern_df = pd.DataFrame(
            self.patterns,
            columns=pattern_col_names,
        )

        pattern_grp = pattern_df.groupby(
            pattern_df.columns.tolist(), as_index=False
        ).size()
        pattern_grp.rename(columns={"size": "num_records"}, inplace=True)
        pattern_grp["potential_matches"] = [[] for _ in range(len(pattern_grp))]
        pattern_grp["num_matched"] = 0
        pattern_grp["num_avail"] = pattern_grp["num_records"]

        # make df of actual records
        msg_col_names = (
            "log_name",
            "log_level",
            "log_msg",
        )
        actual_records = []

        for record in caplog.record_tuples:
            actual_records.append(
                (
                    record[0],
                    record[1],
                    record[2],
                )
            )
        msg_df = pd.DataFrame(
            actual_records,
            columns=msg_col_names,
        )

        msg_grp = msg_df.groupby(msg_df.columns.tolist(), as_index=False).size()
        msg_grp.rename(columns={"size": "num_records"}, inplace=True)
        msg_grp["potential_matches"] = [[] for _ in range(len(msg_grp))]
        msg_grp["num_matched"] = 0
        msg_grp["num_avail"] = msg_grp["num_records"]

        ################################################################
        # set potential matches in both data frames
        ################################################################
        for p_row in pattern_grp.itertuples():
            pattern_str = p_row.pattern
            pattern_regex = re.compile(pattern_str)

            pattern_potentials = []
            for m_row in msg_grp.itertuples():
                if (p_row.fullmatch and pattern_regex.fullmatch(m_row.log_msg)) or (
                    not p_row.fullmatch and pattern_regex.match(m_row.log_msg)
                ):
                    if (
                        p_row.log_name == m_row.log_name
                        and p_row.log_level == m_row.log_level
                    ):
                        pattern_potentials.append(m_row.Index)
                        msg_grp.at[m_row.Index, "potential_matches"].append(p_row.Index)

            pattern_grp.at[p_row.Index, "potential_matches"] = pattern_potentials

        ################################################################
        # settle matches
        ################################################################
        # logger.debug(f"1 pattern_grp: \n{pattern_grp}")
        # logger.debug(f"1 msg_grp: \n{msg_grp}")

        num_loops = 0
        max_potential_matches = 0
        while True:
            num_loops += 1
            avail_pattern_grp = pattern_grp[pattern_grp["num_avail"] > 0]
            if avail_pattern_grp.empty:
                break
            avail_msg_grp = msg_grp[msg_grp["num_avail"] > 0]
            if avail_msg_grp.empty:
                break

            p_len = pd.Series(
                avail_pattern_grp["potential_matches"],
                dtype=pd.ArrowDtype(pa.list_(pa.int64())),
            ).list.len()

            p_len_non_zero = p_len[p_len > 0]

            if p_len_non_zero.empty:
                break

            m_len = pd.Series(
                avail_msg_grp["potential_matches"],
                dtype=pd.ArrowDtype(pa.list_(pa.int64())),
            ).list.len()

            m_len_non_zero = m_len[m_len > 0]

            if m_len_non_zero.empty:
                break

            p_min_potential_matches = min(p_len_non_zero)
            m_min_potential_matches = min(m_len_non_zero)

            min_potential_matches = min(
                p_min_potential_matches, m_min_potential_matches
            )

            max_potential_matches = max(max_potential_matches, min_potential_matches)

            if p_min_potential_matches <= m_min_potential_matches:
                self.search_df(
                    avail_df=avail_pattern_grp,
                    search_arg_df=pattern_grp,
                    search_targ_df=msg_grp,
                    min_potential_matches=min_potential_matches,
                )
            else:
                self.search_df(
                    avail_df=avail_msg_grp,
                    search_arg_df=msg_grp,
                    search_targ_df=pattern_grp,
                    min_potential_matches=min_potential_matches,
                )

        ################################################################
        # reconcile pattern matches
        ################################################################
        # logger.debug(f"2 pattern_grp: \n{pattern_grp}")
        # logger.debug(f"2 msg_grp: \n{msg_grp}")
        num_patterns = pattern_grp["num_records"].sum()
        num_matched_patterns = pattern_grp.num_matched.sum()
        num_unmatched_patterns = num_patterns - num_matched_patterns
        unmatched_pattern_print = ""
        if num_patterns != num_matched_patterns:
            unmatched_pattern_df = pattern_grp[
                pattern_grp.num_records != pattern_grp.num_matched
            ]
            # if unmatched_pattern_df.empty:
            #     unmatched_pattern_print = ""
            # else:
            unmatched_pattern_print = unmatched_pattern_df.to_string(
                columns=[
                    "log_name",
                    "log_level",
                    "pattern",
                    "fullmatch",
                    "num_records",
                    "num_matched",
                ],
                index=False,
            )

        ################################################################
        # reconcile msg matches
        ################################################################
        # logger.debug(f"msg_grp= \n{msg_grp}")
        num_msgs = msg_grp["num_records"].sum()
        num_matched_msgs = msg_grp.num_matched.sum()
        num_unmatched_msgs = num_msgs - num_matched_msgs
        if num_msgs > 0 and num_msgs == num_matched_msgs:
            matched_log_msg_print = msg_grp.to_string(
                columns=[
                    "log_name",
                    "log_level",
                    "log_msg",
                    "num_records",
                    "num_matched",
                ],
                index=False,
            )
            unmatched_log_msg_print = ""
        else:
            matched_actual_df = msg_grp[msg_grp.num_records == msg_grp.num_matched]
            if matched_actual_df.empty:
                matched_log_msg_print = ""
            else:
                matched_log_msg_print = matched_actual_df.to_string(
                    columns=[
                        "log_name",
                        "log_level",
                        "log_msg",
                        "num_records",
                        "num_matched",
                    ],
                    index=False,
                )
            unmatched_actual_df = msg_grp[msg_grp.num_records != msg_grp.num_matched]
            if unmatched_actual_df.empty:
                unmatched_log_msg_print = ""
            else:
                unmatched_log_msg_print = unmatched_actual_df.to_string(
                    columns=[
                        "log_name",
                        "log_level",
                        "log_msg",
                        "num_records",
                        "num_matched",
                    ],
                    index=False,
                )

        return MatchResults(
            num_patterns=num_patterns,
            num_matched_patterns=num_matched_patterns,
            num_unmatched_patterns=num_unmatched_patterns,
            num_log_msgs=num_msgs,
            num_matched_log_msgs=num_matched_msgs,
            num_unmatched_log_msgs=num_unmatched_msgs,
            unmatched_patterns=unmatched_pattern_print,
            unmatched_log_msgs=unmatched_log_msg_print,
            matched_log_msgs=matched_log_msg_print,
        )

    ####################################################################
    # search_df for matches
    ####################################################################
    @staticmethod
    def search_df(
        avail_df: pd.DataFrame,
        search_arg_df: pd.DataFrame,
        search_targ_df: pd.DataFrame,
        min_potential_matches: int,
    ) -> int:
        """Print the match results.

        Args:
            avail_df: data frame of available entries
            search_arg_df: data frame that has the search arg
            search_targ_df: data frame that has the search target
            min_potential_matches: the currently known minimum number of
                non-zero potential matches that need to be processed

        Returns:
            min_potential_matches, which is either the same or lower
        """

        # This method is called for each of the two data frames, the
        # first call having the pattern_df acting as the search_arg_df
        # and the msg_df as the search_targ_df, and the second call with
        # the two data frames in reversed roles.
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
        # print(f"entered search_df {min_potential_matches=}")
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
                    adj_df.at[idx_adjust, "potential_matches"].remove(remove_idx)
                    new_len = len(adj_df.at[idx_adjust, "potential_matches"])
                    if new_len:
                        ret_min_len = min(ret_min_len, new_len)

            return ret_min_len

        for search_item in avail_df.itertuples():
            arg_num_avail = search_item.num_avail
            if len(search_item.potential_matches) == min_potential_matches:
                for potential_idx in search_item.potential_matches:
                    targ_num_avail = search_targ_df.at[potential_idx, "num_avail"]
                    if targ_num_avail > 0:
                        if arg_num_avail == targ_num_avail:
                            search_arg_df.at[
                                search_item.Index, "num_matched"
                            ] += arg_num_avail
                            search_arg_df.at[search_item.Index, "num_avail"] = 0

                            targ_df_idx_adjust_list = (
                                search_item.potential_matches.copy()
                            )
                            targ_df_idx_adjust_list.remove(potential_idx)
                            new_targ_min = min_potential_matches
                            if targ_df_idx_adjust_list:
                                new_targ_min = adjust_potential_matches(
                                    adj_df=search_targ_df,
                                    idx_adjust_list=targ_df_idx_adjust_list,
                                    remove_idx=search_item.Index,
                                    min_len=min_potential_matches,
                                )

                            search_targ_df.at[
                                potential_idx, "num_matched"
                            ] += targ_num_avail
                            search_targ_df.at[potential_idx, "num_avail"] = 0
                            arg_df_idx_adjust_list = search_targ_df.at[
                                potential_idx, "potential_matches"
                            ].copy()
                            arg_df_idx_adjust_list.remove(search_item.Index)
                            new_arg_min = min_potential_matches
                            if arg_df_idx_adjust_list:
                                new_arg_min = adjust_potential_matches(
                                    adj_df=search_arg_df,
                                    idx_adjust_list=arg_df_idx_adjust_list,
                                    remove_idx=potential_idx,
                                    min_len=min_potential_matches,
                                )

                            if new_targ_min < new_arg_min:
                                return new_targ_min
                            min_potential_matches = min(
                                min_potential_matches,
                                new_targ_min,
                                new_arg_min,
                            )
                            # it does not matter whether the new min is
                            # the same or less by any number, this
                            # search_arg is completed, so we break to
                            # get the next search_arg that satisfies the
                            # new min (which could be the remainder or
                            # just the ones we adjusted).
                            break
                        elif arg_num_avail > targ_num_avail:
                            search_arg_df.at[
                                search_item.Index, "num_matched"
                            ] += targ_num_avail

                            arg_num_avail -= targ_num_avail
                            search_arg_df.at[search_item.Index, "num_avail"] = (
                                arg_num_avail
                            )

                            search_targ_df.at[
                                potential_idx, "num_matched"
                            ] += targ_num_avail
                            search_targ_df.at[potential_idx, "num_avail"] = 0
                            arg_df_idx_adjust_list = search_targ_df.at[
                                potential_idx, "potential_matches"
                            ].copy()
                            # arg_df_idx_adjust_list.remove(search_item.Index)
                            new_arg_min = min_potential_matches
                            if arg_df_idx_adjust_list:
                                new_arg_min = adjust_potential_matches(
                                    adj_df=search_arg_df,
                                    idx_adjust_list=arg_df_idx_adjust_list,
                                    remove_idx=potential_idx,
                                    min_len=min_potential_matches,
                                )

                            # we still have some avail, but if this is a
                            # min 1 scan then we won't have any addition
                            # potentials to try.
                            if new_arg_min == min_potential_matches:
                                break
                            else:
                                min_potential_matches = new_arg_min
                        else:  # targ_num_avail > arg_num_avail
                            search_arg_df.at[
                                search_item.Index, "num_matched"
                            ] += arg_num_avail

                            search_arg_df.at[search_item.Index, "num_avail"] = 0
                            targ_df_idx_adjust_list = (
                                search_item.potential_matches.copy()
                            )
                            # targ_df_idx_adjust_list.remove(potential_idx)
                            new_targ_min = min_potential_matches
                            if targ_df_idx_adjust_list:
                                new_targ_min = adjust_potential_matches(
                                    adj_df=search_targ_df,
                                    idx_adjust_list=targ_df_idx_adjust_list,
                                    remove_idx=search_item.Index,
                                    min_len=min_potential_matches,
                                )

                            search_targ_df.at[
                                potential_idx, "num_matched"
                            ] += arg_num_avail
                            search_targ_df.at[potential_idx, "num_avail"] = (
                                targ_num_avail - arg_num_avail
                            )
                            if new_targ_min < min_potential_matches:
                                return new_targ_min

                            # move on since this arg is now depleted
                            # regardless of any additional potential
                            # targets to try
                            break

                # We either found a match or tried each index and found
                # that they were all claimed. Either way, we no longer
                # have a need for potential_matches. Clear it now to
                # avoid the overhead of trying again to find unclaimed
                # potential matches when we know that none exist.
                # search_arg_df.at[search_item.Index, "potential_matches"] = []

        return min_potential_matches

    ####################################################################
    # print_match_results
    ####################################################################
    @staticmethod
    def print_match_results(
        match_results: MatchResults, print_matched: bool = True
    ) -> None:
        """Print the match results.

        Args:
            match_results: contains the results to be printed
            print_matched: if True, print the matched records, otherwise
                skip printing the matched records

        """
        summary_stats_df = pd.DataFrame(
            {
                "item_type": ["patterns", "log_msgs"],
                "num_items": [
                    match_results.num_patterns,
                    match_results.num_log_msgs,
                ],
                "num_matched": [
                    match_results.num_matched_patterns,
                    match_results.num_matched_log_msgs,
                ],
                "num_unmatched": [
                    match_results.num_unmatched_patterns,
                    match_results.num_unmatched_log_msgs,
                ],
            }
        )

        print_flower_box_msg("               summary stats                ")
        print_stats = summary_stats_df.to_string(
            columns=[
                "item_type",
                "num_items",
                "num_matched",
                "num_unmatched",
            ],
            index=False,
        )

        print(print_stats)

        print_flower_box_msg("unmatched patterns:")
        if match_results.unmatched_patterns:
            print(match_results.unmatched_patterns)

        print_flower_box_msg("unmatched log_msgs:")
        if match_results.unmatched_log_msgs:
            print(match_results.unmatched_log_msgs)

        if print_matched:
            print_flower_box_msg(" matched log_msgs: ")
            if match_results.matched_log_msgs:
                print(match_results.matched_log_msgs)

    ####################################################################
    # verify log messages
    ####################################################################
    @staticmethod
    def verify_log_results(
        match_results: MatchResults, check_actual_unmatched: bool = True
    ) -> None:
        """Verify that each log message issued is as expected.

        Args:
            match_results: contains the results to be verified
            check_actual_unmatched: If True, check that there are no
                remaining unmatched actual records

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
            "Use LogVer.validate_match_results() instead",
            category=DeprecationWarning,
            stacklevel=2,
        )
        if match_results.num_unmatched_patterns:
            raise UnmatchedExpectedMessages(
                f"There are {match_results.num_unmatched_patterns} "
                "expected log messages that failed to match actual log "
                "messages."
            )

        if check_actual_unmatched and match_results.num_unmatched_log_msgs:
            raise UnmatchedActualMessages(
                f"There are {match_results.num_unmatched_log_msgs} "
                "actual log messages that failed to match expected log "
                "messages."
            )

    ####################################################################
    # verify_match_results
    ####################################################################
    @staticmethod
    def validate_match_results(match_results: MatchResults) -> None:
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
                f"There {is_are} {match_results.num_unmatched_patterns} {pattern_s} that did not "
                "match any log messages."
            )

        if match_results.num_unmatched_log_msgs:
            if match_results.num_unmatched_log_msgs == 1:
                is_are = "is"
                log_msg_s = "log messages"
            else:
                is_are = "are"
                log_msg_s = "log messages"
            raise UnmatchedLogMessages(
                f"There {is_are} {match_results.num_unmatched_log_msgs} {log_msg_s} that did not "
                "get matched by any patterns."
            )
