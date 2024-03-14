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
from collections import defaultdict
from dataclasses import dataclass
import itertools as it
import logging
import more_itertools as mi
import pandas as pd
import pyarrow as pa
import pytest
import re
import time
from typing import Any, Optional, Type, TYPE_CHECKING, Union

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


@dataclass
class MatchResults:
    """Match results returned by get_match_results method."""

    num_exp_records: int
    num_exp_unmatched: int
    num_actual_records: int
    num_actual_unmatched: int
    num_records_matched: int
    unmatched_exp_records: list[tuple[str, int, Any]]
    unmatched_actual_records: list[tuple[str, int, Any]]
    matched_records: list[tuple[str, int, Any]]


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
        self.expected_messages: list[
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

        Example: add two messages, each at a different level

        .. code-block:: python

            def test_example(caplog: pytest.LogCaptureFixture
                            ) -> None:
                logger = logging.getLogger('add_msg')
                log_ver = LogVer('add_msg')
                log_msg1 = 'hello'
                log_msg2 = 'goodbye'
                log_ver.add_msg(log_msg=log_msg1)
                log_ver.add_msg(log_msg=log_msg2,
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
            self.expected_messages.append(
                (
                    log_name_to_use,
                    log_level,
                    log_msg,
                    True,
                )
            )
        else:
            self.expected_messages.append(
                (
                    log_name_to_use,
                    log_level,
                    log_msg,
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
        start_time = time.time()
        pattern_col_names = (
            "log_name",
            "log_level",
            "log_msg",
            "fullmatch",
        )
        pattern_df = pd.DataFrame(
            self.expected_messages,
            columns=pattern_col_names,
        )

        # print(f"\npattern_df=\n{pattern_df}")

        pattern_grp = pattern_df.groupby(
            pattern_df.columns.tolist(), as_index=False
        ).size()
        pattern_grp["potential_matches"] = [[] for _ in range(len(pattern_grp))]
        pattern_grp["num_matched"] = 0

        # print(f"\npattern_grp=\n{pattern_grp}")
        # pattern_df["potential_matches2"] = pd.Series(
        #     pattern_df["potential_matches"],
        #     dtype=pd.ArrowDtype(pa.list_(pa.int64())),
        # )

        # print(f"\n   init *******************************************")
        # print("\npattern_df=\n", pattern_df)

        # lens = pattern_df["potential_matches2"].list.len()
        # print(f"{lens=}")

        # pattern_df_grp = pattern_df.groupby(
        #     pattern_df.columns.tolist(), as_index=False
        # ).size()

        # make df of actual records
        msg_col_names = (
            "log_name",
            "log_level",
            "log_msg",
        )
        actual_records = []
        # for record in caplog.record_tuples:
        #     actual_records.append((record[0], record[1], record[2], [], False, ""))

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
        # print(f"\nmsg_df=\n{msg_df}")

        msg_grp = msg_df.groupby(msg_df.columns.tolist(), as_index=False).size()
        msg_grp["potential_matches"] = [[] for _ in range(len(msg_grp))]
        msg_grp["num_matched"] = 0
        # print(f"\nmsg_grp=\n{msg_grp}")
        # print(f"\n   init ******************************************")
        # print("\nmsg_df=\n", msg_df)

        # def find_matches(p_m_row):
        #     print(f"{p_m_row=}")
        #     print(f"{p_m_row[0].log_msg=}")
        #     print(f"{p_m_row[1].log_msg=}")
        #
        # mi.consume(
        #     map(find_matches, it.product(pattern_df.itertuples(), msg_df.itertuples()))
        # )
        ################################################################
        # set potential matches in both data frames
        ################################################################
        print(f"DataFrames built: {time.time()-start_time=}")
        for p_row in pattern_grp.itertuples():
            pattern_str = p_row.log_msg
            pattern_regex = re.compile(pattern_str)

            # saved_m_row = None
            # all_matches_same = True
            # print(f"{pattern_str=}")
            # msg_grp2 = msg_grp[pattern_regex.fullmatch(msg_grp.log_msg)]
            # print(f"msg_grp2:\n{msg_grp2}")

            # for m_row in msg_grp2.itertuples():
            #     pattern_grp.at[p_row.Index, "potential_matches"].append(m_row.Index)
            #     msg_grp.at[m_row.Index, "potential_matches"].append(p_row.Index)

            pattern_potentials = []
            for m_row in msg_grp.itertuples():
                if (p_row.fullmatch and pattern_regex.fullmatch(m_row.log_msg)) or (
                    not p_row.fullmatch and pattern_regex.match(m_row.log_msg)
                ):
                    if (
                        p_row.log_name == m_row.log_name
                        and p_row.log_level == m_row.log_level
                    ):
                        # pattern_grp.at[p_row.Index, "potential_matches"].append(m_row.Index)
                        pattern_potentials.append(m_row.Index)
                        msg_grp.at[m_row.Index, "potential_matches"].append(p_row.Index)

            pattern_grp.at[p_row.Index, "potential_matches"] = pattern_potentials
            # if saved_m_row is None:
            #     saved_m_row = m_row
            # else:
            #     if saved_m_row[1:] != m_row[1:]:
            #         all_matches_same = False
            # if (
            #     len(pattern_df.at[p_row.Index, "potential_matches"]) > 0
            #     and all_matches_same
            # ):
            #     msg_df_idx = pattern_df.at[p_row.Index, "potential_matches"][0]
            #     pattern_df.at[p_row.Index, "claimed"] = True
            #     pattern_df.at[p_row.Index, "claimed_by"] = msg_df_idx
            #
            #     msg_df.at[msg_df_idx, "claimed"] = True
            #     msg_df.at[msg_df_idx, "claimed_by"] = p_row.Index
            #
            #     # remove potential_items to prevent counting them
            #     pattern_df.at[p_row.Index, "potential_matches"] = []
            #     msg_df.at[msg_df_idx, "potential_matches"] = []

        print(f"\n****** potential matches set: {time.time()-start_time=}\n")

        # print(f"\npattern_grp=\n{pattern_grp}")
        # print(f"\nmsg_grp=\n{msg_grp}")
        ################################################################
        # settle matches
        ################################################################
        num_loops = 0
        max_potential_matches = 0
        while True:
            num_loops += 1
            # if num_loops % 10 == 0:
            #     print(f"match results {num_loops=}, {time.time()-start_time=} ")
            min_potential_matches = 0

            def count_matches(potential_matches):
                nonlocal min_potential_matches
                len_potential_matches = len(potential_matches)
                if len_potential_matches:
                    if min_potential_matches:
                        min_potential_matches = min(
                            min_potential_matches, len_potential_matches
                        )
                    else:  # min_potential_matches is zero
                        min_potential_matches = len_potential_matches

            pattern_grp["potential_matches"].apply(count_matches)

            msg_grp["potential_matches"].apply(count_matches)

            # p_len = pd.Series(
            #     pattern_df["potential_matches"],
            #     dtype=pd.ArrowDtype(pa.list_(pa.int64())),
            # ).list.len()
            #
            # p_len = p_len[p_len > 0]
            #
            # if not p_len.empty:
            #     min_potential_matches1 = min(p_len)
            # else:
            #     min_potential_matches1 = 0
            #
            # m_len = pd.Series(
            #     msg_df["potential_matches"],
            #     dtype=pd.ArrowDtype(pa.list_(pa.int64())),
            # ).list.len()
            #
            # m_len = m_len[m_len > 0]
            #
            # if not m_len.empty:
            #     min_potential_matches2 = min(m_len)
            # else:
            #     min_potential_matches2 = 0
            #
            # if min_potential_matches1 == 0:
            #     min_potential_matches = min_potential_matches2
            # elif min_potential_matches2 == 0:
            #     min_potential_matches = min_potential_matches1
            # else:
            #     min_potential_matches = min(
            #         min_potential_matches1, min_potential_matches2
            #     )

            if not min_potential_matches:
                break

            if num_loops % 10 == 0:
                print(
                    f"match results {num_loops=}, {min_potential_matches=}, "
                    f"{time.time()-start_time=} "
                )
            max_potential_matches = max(max_potential_matches, min_potential_matches)
            min_potential_matches = self.search_df(
                search_arg_df=pattern_grp,
                search_targ_df=msg_grp,
                min_potential_matches=min_potential_matches,
            )

            self.search_df(
                search_arg_df=msg_grp,
                search_targ_df=pattern_grp,
                min_potential_matches=min_potential_matches,
            )

        ################################################################
        # reconcile pattern matches
        ################################################################
        print(f"\n****** 1 ready to reconcile matches: {time.time()-start_time=}\n")
        unmatched_exp_records = []
        if pattern_grp["size"].sum() != pattern_grp.num_matched.sum():
            unmatched_patterns_to_concat = []
            for p_grp_row in pattern_grp.itertuples():
                num_matched = p_grp_row.num_matched
                log_msg = p_grp_row.log_msg

                unmatched_patterns = pattern_df.loc[
                    pattern_df.log_msg == log_msg, ["log_name", "log_level", "log_msg"]
                ].iloc[num_matched:]

                unmatched_patterns_to_concat.append(unmatched_patterns)

            res_unmatched_patterns = pd.concat(unmatched_patterns_to_concat)
            for pattern_log_msg in res_unmatched_patterns.itertuples():
                unmatched_exp_records.append(
                    (
                        pattern_log_msg.log_name,
                        pattern_log_msg.log_level,
                        pattern_log_msg.log_msg,
                    )
                )

        ################################################################
        # reconcile msg matches
        ################################################################
        print(f"\n****** 2 ready to reconcile matches: {time.time()-start_time=}\n")
        matched_actual_records = []
        unmatched_actual_records = []
        num_msgs = msg_grp["size"].sum()
        num_matched_msgs = msg_grp.num_matched.sum()
        num_unmatched_msgs = num_msgs - num_matched_msgs
        if msg_grp["size"].sum() == msg_grp.num_matched.sum():
            mar_print = msg_grp.to_string(
                columns=["log_name", "log_level", "log_msg", "num_matched"], index=False
            )
            matched_actual_records.append(mar_print)
        else:
            matched_msgs_to_concat = []
            unmatched_msgs_to_concat = []

            for m_grp_row in msg_grp.itertuples():
                num_matched = m_grp_row.num_matched
                log_msg = m_grp_row.log_msg

                matched_msgs = msg_df.loc[
                    msg_df.log_msg == log_msg, ["log_name", "log_level", "log_msg"]
                ].iloc[:num_matched]
                unmatched_msgs = msg_df.loc[
                    msg_df.log_msg == log_msg, ["log_name", "log_level", "log_msg"]
                ].iloc[num_matched:]

                matched_msgs_to_concat.append(matched_msgs)
                unmatched_msgs_to_concat.append(unmatched_msgs)

            res_matched_msgs = pd.concat(matched_msgs_to_concat)
            res_unmatched_msgs = pd.concat(unmatched_msgs_to_concat)

            mar_print = msg_grp.to_string(
                columns=["log_name", "log_level", "log_msg", "num_matched"], index=False
            )
            matched_actual_records.append(mar_print)
            for msg_log_msg in res_unmatched_msgs.itertuples():
                unmatched_actual_records.append(
                    (msg_log_msg.log_name, msg_log_msg.log_level, msg_log_msg.log_msg)
                )

        print(
            f"returning match results {max_potential_matches=}, {num_loops=}, "
            f"{time.time()-start_time=} "
        )
        return MatchResults(
            num_exp_records=len(self.expected_messages),
            num_exp_unmatched=len(unmatched_exp_records),
            num_actual_records=len(caplog.records),
            num_actual_unmatched=len(unmatched_actual_records),
            num_records_matched=len(matched_actual_records),
            unmatched_exp_records=unmatched_exp_records,
            unmatched_actual_records=unmatched_actual_records,
            matched_records=matched_actual_records,
        )

    ####################################################################
    # search_df for matches
    ####################################################################
    @staticmethod
    def search_df(
        search_arg_df: pd.DataFrame,
        search_targ_df: pd.DataFrame,
        min_potential_matches: int,
    ) -> int:
        """Print the match results.

        Args:
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
        for search_item in search_arg_df.itertuples():
            arg_num_avail = search_item.size - search_item.num_matched
            if (
                arg_num_avail > 0
                and len(search_item.potential_matches) == min_potential_matches
            ):
                for potential_idx in search_item.potential_matches:
                    targ_num_avail = (
                        search_targ_df.at[potential_idx, "size"]
                        - search_targ_df.at[potential_idx, "num_matched"]
                    )
                    if targ_num_avail > 0:
                        if arg_num_avail == targ_num_avail:
                            search_arg_df.at[
                                search_item.Index, "num_matched"
                            ] += arg_num_avail
                            search_arg_df.at[search_item.Index, "potential_matches"] = (
                                []
                            )

                            search_targ_df.at[
                                potential_idx, "num_matched"
                            ] += targ_num_avail
                            search_targ_df.at[potential_idx, "potential_matches"] = []
                        elif arg_num_avail > targ_num_avail:
                            search_arg_df.at[
                                search_item.Index, "num_matched"
                            ] += targ_num_avail

                            search_targ_df.at[
                                potential_idx, "num_matched"
                            ] += targ_num_avail
                            search_targ_df.at[potential_idx, "potential_matches"] = []
                        else:
                            search_arg_df.at[
                                search_item.Index, "num_matched"
                            ] += arg_num_avail
                            search_arg_df.at[search_item.Index, "potential_matches"] = (
                                []
                            )
                            search_targ_df.at[
                                potential_idx, "num_matched"
                            ] += arg_num_avail

                        # search_arg_df.at[search_item.Index, "claimed"] = True
                        # search_arg_df.at[search_item.Index, "claimed_by"] = (
                        #     potential_idx
                        # )
                        #
                        # search_targ_df.at[potential_idx, "claimed"] = True
                        # search_targ_df.at[potential_idx, "claimed_by"] = (
                        #     search_item.Index
                        # )

                        # remove potential_items to prevent counting them
                        # search_arg_df.at[search_item.Index, "potential_matches"] = []
                        # search_targ_df.at[potential_idx, "potential_matches"] = []

                        def remove_match(potential_matches, idx):
                            nonlocal min_potential_matches
                            if idx in potential_matches:
                                potential_matches.remove(idx)
                            len_potential_matches = len(potential_matches)
                            if len_potential_matches:
                                min_potential_matches = min(
                                    min_potential_matches, len_potential_matches
                                )
                            return potential_matches

                        search_arg_df["potential_matches"] = search_arg_df[
                            "potential_matches"
                        ].apply(remove_match, idx=potential_idx)
                        search_targ_df["potential_matches"] = search_targ_df[
                            "potential_matches"
                        ].apply(remove_match, idx=search_item.Index)

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
        max_num = max(
            match_results.num_exp_records,
            match_results.num_exp_unmatched,
            match_results.num_actual_records,
            match_results.num_actual_unmatched,
            match_results.num_records_matched,
        )
        max_len = len(str(max_num))
        msg1 = (
            "number expected log records: "
            f"{match_results.num_exp_records:>{max_len}}"
        )
        msg2 = (
            "number expected unmatched  : "
            f"{match_results.num_exp_unmatched:>{max_len}}"
        )
        msg3 = (
            "number actual log records  : "
            f"{match_results.num_actual_records:>{max_len}}"
        )
        msg4 = (
            "number actual unmatched    : "
            f"{match_results.num_actual_unmatched:>{max_len}}"
        )
        msg5 = (
            "number matched records     : "
            f"{match_results.num_records_matched:>{max_len}}"
        )

        print_flower_box_msg([msg1, msg2, msg3, msg4, msg5])

        legend_msg = "(logger name, level, message)"
        print_flower_box_msg(["unmatched expected records", legend_msg])
        for log_msg in match_results.unmatched_exp_records:
            print(log_msg)

        print_flower_box_msg(["unmatched actual records", legend_msg])
        for log_msg in match_results.unmatched_actual_records:
            print(log_msg)

        if print_matched:
            print_flower_box_msg(["matched records", legend_msg])
            for log_msg in match_results.matched_records:
                print(log_msg)

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

        Raises:
            UnmatchedExpectedMessages: There are expected log messages
                that failed to match actual log messages.
            UnmatchedActualMessages: There are actual log messages that
                failed to match expected log messages.

        """
        if match_results.num_exp_unmatched:
            raise UnmatchedExpectedMessages(
                f"There are {match_results.num_exp_unmatched} "
                "expected log messages that failed to match actual log "
                "messages."
            )

        if check_actual_unmatched and match_results.num_actual_unmatched:
            raise UnmatchedActualMessages(
                f"There are {match_results.num_actual_unmatched} "
                "actual log messages that failed to match expected log "
                "messages."
            )

    # ####################################################################
    # # get_match_results
    # ####################################################################
    # def get_match_results(self, caplog: pytest.LogCaptureFixture) -> MatchResults:
    #     """Match the expected to actual log records.
    #
    #     Args:
    #         caplog: pytest fixture that captures log messages
    #
    #     Returns:
    #         Number of expected records, number of actual records,
    #           number of matching records, list of unmatched expected
    #           records, list of unmatched actual records, and list
    #           or matching records
    #
    #     """
    #     # make a work copy of fullmatch expected records
    #     unmatched_exp_records_fullmatch: list[
    #         tuple[str, int, Any]
    #     ] = self.expected_messages_fullmatch.copy()
    #
    #     # make a work copy of expected records
    #     unmatched_exp_records: list[
    #         tuple[str, int, Any]
    #     ] = self.expected_messages.copy()
    #
    #     # make a work copy of actual records
    #     unmatched_actual_records: list[
    #         tuple[str, int, Any]
    #     ] = caplog.record_tuples.copy()
    #
    #     matched_records: list[tuple[str, int, Any]] = []
    #
    #     ################################################################
    #     # find matches, update working copies to reflect results
    #     ################################################################
    #     if unmatched_exp_records_fullmatch:  # if fullmatch records
    #         for actual_record in caplog.record_tuples:
    #             # look for fullmatch
    #             for idx, exp_record in enumerate(unmatched_exp_records_fullmatch):
    #                 # check that the logger name, level, and message
    #                 # match
    #                 if (
    #                     exp_record[0] == actual_record[0]
    #                     and exp_record[1] == actual_record[1]
    #                     and exp_record[2].fullmatch(actual_record[2])
    #                 ):
    #                     unmatched_exp_records_fullmatch.pop(idx)
    #                     unmatched_actual_records.remove(actual_record)
    #                     matched_records.append(
    #                         (actual_record[0], actual_record[1], actual_record[2])
    #                     )
    #                     break
    #
    #     if unmatched_exp_records:  # if partial match records
    #         for actual_record in unmatched_actual_records.copy():
    #             # look for partial match in unmatched_exp_records
    #             for idx, exp_record in enumerate(unmatched_exp_records):
    #                 # check that the logger name, level, and message
    #                 # match
    #                 if (
    #                     exp_record[0] == actual_record[0]
    #                     and exp_record[1] == actual_record[1]
    #                     and exp_record[2].match(actual_record[2])
    #                 ):
    #                     unmatched_exp_records.pop(idx)
    #                     unmatched_actual_records.remove(actual_record)
    #                     matched_records.append(
    #                         (actual_record[0], actual_record[1], actual_record[2])
    #                     )
    #                     break
    #
    #     # convert unmatched expected records to string form
    #     unmatched_exp_records_2 = []
    #     for item in unmatched_exp_records_fullmatch:
    #         unmatched_exp_records_2.append((item[0], item[1], item[2].pattern))
    #
    #     for item in unmatched_exp_records:
    #         unmatched_exp_records_2.append((item[0], item[1], item[2].pattern))
    #
    #     return MatchResults(
    #         num_exp_records=(
    #             len(self.expected_messages) + len(self.expected_messages_fullmatch)
    #         ),
    #         num_exp_unmatched=len(unmatched_exp_records_2),
    #         num_actual_records=len(caplog.records),
    #         num_actual_unmatched=len(unmatched_actual_records),
    #         num_records_matched=len(matched_records),
    #         unmatched_exp_records=unmatched_exp_records_2,
    #         unmatched_actual_records=unmatched_actual_records,
    #         matched_records=matched_records,
    #     )

    # ####################################################################
    # # get_match_results
    # ####################################################################
    # def get_match_results(self, caplog: pytest.LogCaptureFixture) -> MatchResults:
    #     """Match the expected to actual log records.
    #
    #     Args:
    #         caplog: pytest fixture that captures log messages
    #
    #     Returns:
    #         Number of expected records, number of actual records,
    #           number of matching records, list of unmatched expected
    #           records, list of unmatched actual records, and list
    #           or matching records
    #
    #     """
    #     start_time = time.time()
    #     pattern_col_names = (
    #         "log_name",
    #         "log_level",
    #         "item",
    #         "fullmatch",
    #         "potential_matches",
    #         "claimed",
    #         "claimed_by",
    #     )
    #     pattern_df = pd.DataFrame(
    #         self.expected_messages,
    #         columns=pattern_col_names,
    #     )
    #     # pattern_df["potential_matches2"] = pd.Series(
    #     #     pattern_df["potential_matches"],
    #     #     dtype=pd.ArrowDtype(pa.list_(pa.int64())),
    #     # )
    #
    #     # print(f"\n   init *******************************************")
    #     # print("\npattern_df=\n", pattern_df)
    #
    #     # lens = pattern_df["potential_matches2"].list.len()
    #     # print(f"{lens=}")
    #
    #     # pattern_df_grp = pattern_df.groupby(
    #     #     pattern_df.columns.tolist(), as_index=False
    #     # ).size()
    #
    #     # make df of actual records
    #     msg_col_names = (
    #         "log_name",
    #         "log_level",
    #         "item",
    #         "potential_matches",
    #         "claimed",
    #         "claimed_by",
    #     )
    #     actual_records = []
    #     # for record in caplog.record_tuples:
    #     #     actual_records.append((record[0], record[1], record[2], [], False, ""))
    #
    #     for record in caplog.record_tuples:
    #         actual_records.append((record[0], record[1], record[2], [], False, ""))
    #     msg_df = pd.DataFrame(
    #         actual_records,
    #         columns=msg_col_names,
    #     )
    #     # print(f"\n   init ******************************************")
    #     # print("\nmsg_df=\n", msg_df)
    #
    #     # def find_matches(p_m_row):
    #     #     print(f"{p_m_row=}")
    #     #     print(f"{p_m_row[0].item=}")
    #     #     print(f"{p_m_row[1].item=}")
    #     #
    #     # mi.consume(
    #     #     map(find_matches, it.product(pattern_df.itertuples(), msg_df.itertuples()))
    #     # )
    #     ################################################################
    #     # set potential matches in both data frames
    #     ################################################################
    #     # print(f"DataFrames built: {time.time()-start_time=}")
    #     for p_row in pattern_df.itertuples():
    #         pattern_str = p_row.item
    #         pattern_regex = re.compile(pattern_str)
    #
    #         saved_m_row = None
    #         all_matches_same = True
    #         for m_row in msg_df.itertuples():
    #             if not m_row.claimed:
    #                 if (p_row.fullmatch and pattern_regex.fullmatch(m_row.item)) or (
    #                     not p_row.fullmatch and pattern_regex.match(m_row.item)
    #                 ):
    #                     if (
    #                         p_row.log_name == m_row.log_name
    #                         and p_row.log_level == m_row.log_level
    #                     ):
    #                         pattern_df.at[p_row.Index, "potential_matches"].append(
    #                             m_row.Index
    #                         )
    #                         msg_df.at[m_row.Index, "potential_matches"].append(
    #                             p_row.Index
    #                         )
    #                         if saved_m_row is None:
    #                             saved_m_row = m_row
    #                         else:
    #                             if saved_m_row[1:] != m_row[1:]:
    #                                 all_matches_same = False
    #         # if (
    #         #     len(pattern_df.at[p_row.Index, "potential_matches"]) > 0
    #         #     and all_matches_same
    #         # ):
    #         #     msg_df_idx = pattern_df.at[p_row.Index, "potential_matches"][0]
    #         #     pattern_df.at[p_row.Index, "claimed"] = True
    #         #     pattern_df.at[p_row.Index, "claimed_by"] = msg_df_idx
    #         #
    #         #     msg_df.at[msg_df_idx, "claimed"] = True
    #         #     msg_df.at[msg_df_idx, "claimed_by"] = p_row.Index
    #         #
    #         #     # remove potential_items to prevent counting them
    #         #     pattern_df.at[p_row.Index, "potential_matches"] = []
    #         #     msg_df.at[msg_df_idx, "potential_matches"] = []
    #
    #     # print(f"potential matches set: {time.time()-start_time=}")
    #     ################################################################
    #     # settle matches
    #     ################################################################
    #     num_loops = 0
    #     max_potential_matches = 0
    #     while True:
    #         num_loops += 1
    #         # if num_loops % 10 == 0:
    #         #     print(f"match results {num_loops=}, {time.time()-start_time=} ")
    #         min_potential_matches = 0
    #
    #         def count_matches(potential_matches):
    #             nonlocal min_potential_matches
    #             len_potential_matches = len(potential_matches)
    #             if len_potential_matches:
    #                 if min_potential_matches:
    #                     min_potential_matches = min(
    #                         min_potential_matches, len_potential_matches
    #                     )
    #                 else:  # min_potential_matches is zero
    #                     min_potential_matches = len_potential_matches
    #
    #         pattern_df["potential_matches"].apply(count_matches)
    #
    #         msg_df["potential_matches"].apply(count_matches)
    #
    #         # p_len = pd.Series(
    #         #     pattern_df["potential_matches"],
    #         #     dtype=pd.ArrowDtype(pa.list_(pa.int64())),
    #         # ).list.len()
    #         #
    #         # p_len = p_len[p_len > 0]
    #         #
    #         # if not p_len.empty:
    #         #     min_potential_matches1 = min(p_len)
    #         # else:
    #         #     min_potential_matches1 = 0
    #         #
    #         # m_len = pd.Series(
    #         #     msg_df["potential_matches"],
    #         #     dtype=pd.ArrowDtype(pa.list_(pa.int64())),
    #         # ).list.len()
    #         #
    #         # m_len = m_len[m_len > 0]
    #         #
    #         # if not m_len.empty:
    #         #     min_potential_matches2 = min(m_len)
    #         # else:
    #         #     min_potential_matches2 = 0
    #         #
    #         # if min_potential_matches1 == 0:
    #         #     min_potential_matches = min_potential_matches2
    #         # elif min_potential_matches2 == 0:
    #         #     min_potential_matches = min_potential_matches1
    #         # else:
    #         #     min_potential_matches = min(
    #         #         min_potential_matches1, min_potential_matches2
    #         #     )
    #
    #         if not min_potential_matches:
    #             break
    #
    #         # if num_loops % 10 == 0:
    #         #     print(
    #         #         f"match results {num_loops=}, {min_potential_matches=}, "
    #         #         f"{time.time()-start_time=} "
    #         #     )
    #         max_potential_matches = max(max_potential_matches, min_potential_matches)
    #         min_potential_matches = self.search_df(
    #             search_arg_df=pattern_df,
    #             search_targ_df=msg_df,
    #             min_potential_matches=min_potential_matches,
    #         )
    #
    #         self.search_df(
    #             search_arg_df=msg_df,
    #             search_targ_df=pattern_df,
    #             min_potential_matches=min_potential_matches,
    #         )
    #
    #     unmatched_exp_records = []
    #     unmatched_actual_records = []
    #     matched_records = []
    #     for pattern_item in pattern_df.itertuples():
    #         if not pattern_item.claimed:
    #             unmatched_exp_records.append(
    #                 (pattern_item.log_name, pattern_item.log_level, pattern_item.item)
    #             )
    #
    #     for msg_item in msg_df.itertuples():
    #         if msg_item.claimed:
    #             matched_records.append(
    #                 (msg_item.log_name, msg_item.log_level, msg_item.item)
    #             )
    #         else:
    #             unmatched_actual_records.append(
    #                 (msg_item.log_name, msg_item.log_level, msg_item.item)
    #             )
    #     #
    #     # print(
    #     #     f"returning match results {max_potential_matches=}, {num_loops=}, "
    #     #     f"{time.time()-start_time=} "
    #     # )
    #     return MatchResults(
    #         num_exp_records=len(self.expected_messages),
    #         num_exp_unmatched=len(unmatched_exp_records),
    #         num_actual_records=len(caplog.records),
    #         num_actual_unmatched=len(unmatched_actual_records),
    #         num_records_matched=len(matched_records),
    #         unmatched_exp_records=unmatched_exp_records,
    #         unmatched_actual_records=unmatched_actual_records,
    #         matched_records=matched_records,
    #     )

    ####################################################################
    # get_match_results
    ####################################################################
    # def get_match_results(self, caplog: pytest.LogCaptureFixture) -> MatchResults:
    #     """Match the expected to actual log records.
    #
    #     Args:
    #         caplog: pytest fixture that captures log messages
    #
    #     Returns:
    #         Number of expected records, number of actual records,
    #           number of matching records, list of unmatched expected
    #           records, list of unmatched actual records, and list
    #           or matching records
    #
    #     """
    #     start_time = time.time()
    #     pattern_col_names = (
    #         "log_name",
    #         "log_level",
    #         "item",
    #         "fullmatch",
    #         "potential_matches",
    #         "claimed",
    #         "claimed_by",
    #     )
    #     pattern_df = pd.DataFrame(
    #         self.expected_messages,
    #         columns=pattern_col_names,
    #     )
    #     # pattern_df["potential_matches2"] = pd.Series(
    #     #     pattern_df["potential_matches"],
    #     #     dtype=pd.ArrowDtype(pa.list_(pa.int64())),
    #     # )
    #
    #     # print(f"\n   init *******************************************")
    #     # print("\npattern_df=\n", pattern_df)
    #
    #     # lens = pattern_df["potential_matches2"].list.len()
    #     # print(f"{lens=}")
    #
    #     # pattern_df_grp = pattern_df.groupby(
    #     #     pattern_df.columns.tolist(), as_index=False
    #     # ).size()
    #
    #     # make df of actual records
    #     msg_col_names = (
    #         "log_name",
    #         "log_level",
    #         "item",
    #         "potential_matches",
    #         "claimed",
    #         "claimed_by",
    #     )
    #     actual_records = []
    #     # for record in caplog.record_tuples:
    #     #     actual_records.append((record[0], record[1], record[2], [], False, ""))
    #
    #     for record in caplog.record_tuples:
    #         actual_records.append((record[0], record[1], record[2], [], False, ""))
    #     msg_df = pd.DataFrame(
    #         actual_records,
    #         columns=msg_col_names,
    #     )
    #     # print(f"\n   init ******************************************")
    #     # print("\nmsg_df=\n", msg_df)
    #
    #     # def find_matches(p_m_row):
    #     #     print(f"{p_m_row=}")
    #     #     print(f"{p_m_row[0].item=}")
    #     #     print(f"{p_m_row[1].item=}")
    #     #
    #     # mi.consume(
    #     #     map(find_matches, it.product(pattern_df.itertuples(), msg_df.itertuples()))
    #     # )
    #     ################################################################
    #     # set potential matches in both data frames
    #     ################################################################
    #     # print(f"DataFrames built: {time.time()-start_time=}")
    #     for p_row in pattern_df.itertuples():
    #         pattern_str = p_row.item
    #         pattern_regex = re.compile(pattern_str)
    #
    #         saved_m_row = None
    #         all_matches_same = True
    #         for m_row in msg_df.itertuples():
    #             if not m_row.claimed:
    #                 if (p_row.fullmatch and pattern_regex.fullmatch(m_row.item)) or (
    #                     not p_row.fullmatch and pattern_regex.match(m_row.item)
    #                 ):
    #                     if (
    #                         p_row.log_name == m_row.log_name
    #                         and p_row.log_level == m_row.log_level
    #                     ):
    #                         pattern_df.at[p_row.Index, "potential_matches"].append(
    #                             m_row.Index
    #                         )
    #                         msg_df.at[m_row.Index, "potential_matches"].append(
    #                             p_row.Index
    #                         )
    #                         if saved_m_row is None:
    #                             saved_m_row = m_row
    #                         else:
    #                             if saved_m_row[1:] != m_row[1:]:
    #                                 all_matches_same = False
    #         # if (
    #         #     len(pattern_df.at[p_row.Index, "potential_matches"]) > 0
    #         #     and all_matches_same
    #         # ):
    #         #     msg_df_idx = pattern_df.at[p_row.Index, "potential_matches"][0]
    #         #     pattern_df.at[p_row.Index, "claimed"] = True
    #         #     pattern_df.at[p_row.Index, "claimed_by"] = msg_df_idx
    #         #
    #         #     msg_df.at[msg_df_idx, "claimed"] = True
    #         #     msg_df.at[msg_df_idx, "claimed_by"] = p_row.Index
    #         #
    #         #     # remove potential_items to prevent counting them
    #         #     pattern_df.at[p_row.Index, "potential_matches"] = []
    #         #     msg_df.at[msg_df_idx, "potential_matches"] = []
    #
    #     # print(f"potential matches set: {time.time()-start_time=}")
    #     ################################################################
    #     # settle matches
    #     ################################################################
    #     num_loops = 0
    #     max_potential_matches = 0
    #     while True:
    #         num_loops += 1
    #         # if num_loops % 10 == 0:
    #         #     print(f"match results {num_loops=}, {time.time()-start_time=} ")
    #         min_potential_matches = 0
    #
    #         def count_matches(potential_matches):
    #             nonlocal min_potential_matches
    #             len_potential_matches = len(potential_matches)
    #             if len_potential_matches:
    #                 if min_potential_matches:
    #                     min_potential_matches = min(
    #                         min_potential_matches, len_potential_matches
    #                     )
    #                 else:  # min_potential_matches is zero
    #                     min_potential_matches = len_potential_matches
    #
    #         pattern_df["potential_matches"].apply(count_matches)
    #
    #         msg_df["potential_matches"].apply(count_matches)
    #
    #         # p_len = pd.Series(
    #         #     pattern_df["potential_matches"],
    #         #     dtype=pd.ArrowDtype(pa.list_(pa.int64())),
    #         # ).list.len()
    #         #
    #         # p_len = p_len[p_len > 0]
    #         #
    #         # if not p_len.empty:
    #         #     min_potential_matches1 = min(p_len)
    #         # else:
    #         #     min_potential_matches1 = 0
    #         #
    #         # m_len = pd.Series(
    #         #     msg_df["potential_matches"],
    #         #     dtype=pd.ArrowDtype(pa.list_(pa.int64())),
    #         # ).list.len()
    #         #
    #         # m_len = m_len[m_len > 0]
    #         #
    #         # if not m_len.empty:
    #         #     min_potential_matches2 = min(m_len)
    #         # else:
    #         #     min_potential_matches2 = 0
    #         #
    #         # if min_potential_matches1 == 0:
    #         #     min_potential_matches = min_potential_matches2
    #         # elif min_potential_matches2 == 0:
    #         #     min_potential_matches = min_potential_matches1
    #         # else:
    #         #     min_potential_matches = min(
    #         #         min_potential_matches1, min_potential_matches2
    #         #     )
    #
    #         if not min_potential_matches:
    #             break
    #
    #         # if num_loops % 10 == 0:
    #         #     print(
    #         #         f"match results {num_loops=}, {min_potential_matches=}, "
    #         #         f"{time.time()-start_time=} "
    #         #     )
    #         max_potential_matches = max(max_potential_matches, min_potential_matches)
    #         min_potential_matches = self.search_df(
    #             search_arg_df=pattern_df,
    #             search_targ_df=msg_df,
    #             min_potential_matches=min_potential_matches,
    #         )
    #
    #         self.search_df(
    #             search_arg_df=msg_df,
    #             search_targ_df=pattern_df,
    #             min_potential_matches=min_potential_matches,
    #         )
    #
    #     unmatched_exp_records = []
    #     unmatched_actual_records = []
    #     matched_records = []
    #     for pattern_item in pattern_df.itertuples():
    #         if not pattern_item.claimed:
    #             unmatched_exp_records.append(
    #                 (pattern_item.log_name, pattern_item.log_level, pattern_item.item)
    #             )
    #
    #     for msg_item in msg_df.itertuples():
    #         if msg_item.claimed:
    #             matched_records.append(
    #                 (msg_item.log_name, msg_item.log_level, msg_item.item)
    #             )
    #         else:
    #             unmatched_actual_records.append(
    #                 (msg_item.log_name, msg_item.log_level, msg_item.item)
    #             )
    #     #
    #     # print(
    #     #     f"returning match results {max_potential_matches=}, {num_loops=}, "
    #     #     f"{time.time()-start_time=} "
    #     # )
    #     return MatchResults(
    #         num_exp_records=len(self.expected_messages),
    #         num_exp_unmatched=len(unmatched_exp_records),
    #         num_actual_records=len(caplog.records),
    #         num_actual_unmatched=len(unmatched_actual_records),
    #         num_records_matched=len(matched_records),
    #         unmatched_exp_records=unmatched_exp_records,
    #         unmatched_actual_records=unmatched_actual_records,
    #         matched_records=matched_records,
    #     )

    ####################################################################
    # search_df for matches
    ####################################################################
    # @staticmethod
    # def search_df(
    #     search_arg_df: pd.DataFrame,
    #     search_targ_df: pd.DataFrame,
    #     min_potential_matches: int,
    # ) -> int:
    #     """Print the match results.
    #
    #     Args:
    #         search_arg_df: data frame that has the search arg
    #         search_targ_df: data frame that has the search target
    #         min_potential_matches: the currently known minimum number of
    #             non-zero potential matches that need to be processed
    #
    #     Returns:
    #         min_potential_matches, which is either the same or lower
    #     """
    #     # This method is called for each of the two data frames, the
    #     # first call having the pattern_df acting as the search_arg_df
    #     # and the msg_df as the search_targ_df, and the second call with
    #     # the two data frames in reversed roles.
    #     # We iterate ove the search_arg_df, selecting only entries whose
    #     # number of potential_matches is equal to min_potential_matches.
    #     # The idea is to make sure we give entries with few choices a
    #     # chance to claim matches before entries with more choices
    #     # claim them.
    #     # Once we make a claim, we remove the choice from all entries,
    #     # which now means some entries may now have fewer choices than
    #     # min_potential_matches. In order to avoid these entries from
    #     # facing that same scenario of having their limited choices
    #     # "stolen" by an entry with more choices, we need to reduce
    #     # min_potential_matches dynamically.
    #     # We stop calling when we determine no additional matches are
    #     # possible as indicated when all entries have either made a
    #     # match are have exhausted their potential_matches.
    #     for search_item in search_arg_df.itertuples():
    #         if (
    #             not search_item.claimed
    #             and len(search_item.potential_matches) == min_potential_matches
    #         ):
    #             for potential_idx in search_item.potential_matches:
    #                 if not search_targ_df.at[potential_idx, "claimed"]:
    #                     search_arg_df.at[search_item.Index, "claimed"] = True
    #                     search_arg_df.at[search_item.Index, "claimed_by"] = (
    #                         potential_idx
    #                     )
    #
    #                     search_targ_df.at[potential_idx, "claimed"] = True
    #                     search_targ_df.at[potential_idx, "claimed_by"] = (
    #                         search_item.Index
    #                     )
    #
    #                     # remove potential_items to prevent counting them
    #                     search_arg_df.at[search_item.Index, "potential_matches"] = []
    #                     search_targ_df.at[potential_idx, "potential_matches"] = []
    #
    #                     def remove_match(potential_matches, idx):
    #                         nonlocal min_potential_matches
    #                         if idx in potential_matches:
    #                             potential_matches.remove(idx)
    #                         len_potential_matches = len(potential_matches)
    #                         if len_potential_matches:
    #                             min_potential_matches = min(
    #                                 min_potential_matches, len_potential_matches
    #                             )
    #                         return potential_matches
    #
    #                     search_arg_df["potential_matches"] = search_arg_df[
    #                         "potential_matches"
    #                     ].apply(remove_match, idx=potential_idx)
    #                     search_targ_df["potential_matches"] = search_targ_df[
    #                         "potential_matches"
    #                     ].apply(remove_match, idx=search_item.Index)
    #
    #                     break
    #             # We either found a match or tried each index and found
    #             # that they were all claimed. Either way, we no longer
    #             # have a need for potential_matches. Clear it now to
    #             # avoid the overhead of trying again to find unclaimed
    #             # potential matches when we know that none exist.
    #             search_arg_df.at[search_item.Index, "potential_matches"] = []
    #
    #     return min_potential_matches


# print(f"\n*************************************************")
# print("\nmsg_df=\n", msg_df)

# df_log_msgs_grp = df_log_msgs.groupby(
#     df_log_msgs.columns.tolist(), as_index=False
# ).size()
# print(f"\ndf_log_msgs_grp=\n{df_log_msgs_grp}")

# to_repl = df_regex_fullmatch_grp.regex_pattern.values.tolist()
# vals = df_regex_fullmatch_grp["size"].to_list()
# vals = df_regex_fullmatch_grp.index.to_list()
# vals2 = df_regex_fullmatch_grp.regex_pattern.values.tolist()

# print(f"{to_repl=}")
# print(f"{vals=}")

# df_log_msgs_grp["fullmatch_idx"] = df_log_msgs_grp["log_msg"].replace(
#     to_repl, vals, regex=True
# )
# df_log_msgs_grp["exp_used_to_find"] = df_log_msgs_grp["log_msg"].replace(
#     to_repl, vals2, regex=True
# )

# print(f"\n #### df_log_msgs_grp=\n{df_log_msgs_grp}")
# print(f"\n #### df_log_msgs_grp.info()=\n{df_log_msgs_grp.info()}")

# count_result = df_log_msgs_grp["size"] == df_log_msgs_grp["found_size"]

# print(f"count_result=\n{count_result}")

# not_found = df_log_msgs_grp["log_msg"] == df_log_msgs_grp["fullmatch_idx"]
#
# # print(f"\nnot_found=\n{not_found}")
#
# df_log_msgs_grp["fullmatch_idx"] = df_log_msgs_grp["fullmatch_idx"].mask(
#     not_found, -1
# )

# print(f"\n #### 2 {df_log_msgs_grp=}")
# print(f"\n #### 2 {df_log_msgs_grp.info()=}")

# df_log_msgs_grp["diff_nums"] = (
#     df_log_msgs_grp["size"] - df_log_msgs_grp["found_size"]
# )

# print(f"\n #### 3 {df_log_msgs_grp=}")
# print(f"\n #### 3 {df_log_msgs_grp.info()=}")

# to_repl = df_log_msgs_grp.exp_used_to_find.values.tolist()
# vals = df_log_msgs_grp["size"].to_list()
# # vals2 = df_regex_fullmatch_grp.regex_pattern.values.tolist()
#
# df_regex_fullmatch_grp["found_size2"] = df_regex_fullmatch_grp[
#     "regex_pattern"
# ].replace(to_repl, vals, regex=False)
#
# not_found = (
#     df_regex_fullmatch_grp["regex_pattern"]
#     == df_regex_fullmatch_grp["found_size2"]
# )
#
# # print(f"{not_found=}")
#
# df_regex_fullmatch_grp["found_size2"] = df_regex_fullmatch_grp[
#     "found_size2"
# ].mask(not_found, 0)

# df_regex_fullmatch_grp["diff_nums"] = (
#     df_regex_fullmatch_grp["size"] - df_regex_fullmatch_grp["found_size2"]
# )
# print(f"\n #### 4 {df_regex_fullmatch_grp=}")
# print(f"\n #### 4 {df_regex_fullmatch_grp.info()=}")

################################################################
# find matches, update working copies to reflect results
################################################################
# def run_full_match(actual_record):
#     # nonlocal unmatched_exp_records_fullmatch
#     # nonlocal unmatched_actual_records
#     # nonlocal matched_records
#
#     for idx, exp_record in enumerate(unmatched_exp_records_fullmatch):
#         # check that the logger name, level, and message
#         # match
#         if (
#             exp_record[0] == actual_record[0]
#             and exp_record[1] == actual_record[1]
#             and re.compile(exp_record[2]).fullmatch(actual_record[2])
#         ):
#             unmatched_exp_records_fullmatch.pop(idx)
#             unmatched_actual_records.remove(actual_record)
#             matched_records.append(
#                 (actual_record[0], actual_record[1], actual_record[2])
#             )
#             break
#
# if unmatched_exp_records_fullmatch:  # if fullmatch records
#     # print(f" 42 get_match_results")
#     list(map(run_full_match, caplog.record_tuples))
#     # look for fullmatch
#     # for idx, exp_record in enumerate(unmatched_exp_records_fullmatch):
#     #     # check that the logger name, level, and message
#     #     # match
#     #     if (
#     #         exp_record[0] == actual_record[0]
#     #         and exp_record[1] == actual_record[1]
#     #         and exp_record[2].fullmatch(actual_record[2])
#     #     ):
#     #         unmatched_exp_records_fullmatch.pop(idx)
#     #         unmatched_actual_records.remove(actual_record)
#     #         matched_records.append(
#     #             (actual_record[0], actual_record[1], actual_record[2])
#     #         )
#     #         break
#
# def run_partial_match(actual_record):
#     for idx, exp_record in enumerate(unmatched_exp_records):
#         # check that the logger name, level, and message
#         # match
#         if (
#             exp_record[0] == actual_record[0]
#             and exp_record[1] == actual_record[1]
#             and re.compile(exp_record[2]).match(actual_record[2])
#         ):
#             unmatched_exp_records.pop(idx)
#             unmatched_actual_records.remove(actual_record)
#             matched_records.append(
#                 (actual_record[0], actual_record[1], actual_record[2])
#             )
#             break
#
# if unmatched_exp_records:  # if partial match records
#     # for actual_record in unmatched_actual_records.copy():
#     list(map(run_partial_match, unmatched_actual_records.copy()))
#     # look for partial match in unmatched_exp_records
#     # for idx, exp_record in enumerate(unmatched_exp_records):
#     #     # check that the logger name, level, and message
#     #     # match
#     #     if (
#     #         exp_record[0] == actual_record[0]
#     #         and exp_record[1] == actual_record[1]
#     #         and exp_record[2].match(actual_record[2])
#     #     ):
#     #         unmatched_exp_records.pop(idx)
#     #         unmatched_actual_records.remove(actual_record)
#     #         matched_records.append(
#     #             (actual_record[0], actual_record[1], actual_record[2])
#     #         )
#     #         break
#
# # convert unmatched expected records to string form
# unmatched_exp_records_2 = []
# # for item in unmatched_exp_records_fullmatch:
# #     unmatched_exp_records_2.append((item[0], item[1], item[2].pattern))
# #
# # for item in unmatched_exp_records:
# #     unmatched_exp_records_2.append((item[0], item[1], item[2].pattern))
#
# for item in unmatched_exp_records_fullmatch:
#     unmatched_exp_records_2.append((item[0], item[1], item[2]))
#
# for item in unmatched_exp_records:
#     unmatched_exp_records_2.append((item[0], item[1], item[2]))
#
# return MatchResults(
#     num_exp_records=(
#         len(self.expected_messages) + len(self.expected_messages_fullmatch)
#     ),
#     num_exp_unmatched=len(unmatched_exp_records),
#     num_actual_records=len(caplog.records),
#     num_actual_unmatched=len(unmatched_actual_records),
#     num_records_matched=len(matched_records),
#     unmatched_exp_records=unmatched_exp_records,
#     unmatched_actual_records=unmatched_actual_records,
#     matched_records=matched_records,
# )

########################################################################
"""
***********************************
* number expected log records: 18 *
* number expected unmatched  :  0 *
* number actual log records  : 22 *
* number actual unmatched    :  4 *
* number matched records     : 18 *
***********************************

*********************************
* unmatched expected records    *
* (logger name, level, message) *
*********************************

*********************************
* unmatched actual records      *
* (logger name, level, message) *
*********************************
('test_scottbrian_utils.test_entry_trace', 10, "##################### final_plist_combo.plist='po_1, /'")
('test_scottbrian_utils.test_entry_trace', 10, "##################### final_plist_combo.plist='po_1, /'")
('test_scottbrian_utils.test_entry_trace', 10, "##################### final_plist_combo.plist='po_1=1, /'")
('test_scottbrian_utils.test_entry_trace', 10, "##################### final_plist_combo.plist='po_1=1, /'")

*********************************
* matched records               *
* (logger name, level, message) *
*********************************
('test_scottbrian_utils.test_entry_trace', 10, "##################### arg_spec_ret_res.arg_spec='10'")
('scottbrian_utils.entry_trace', 10, '<string>:f1:? entry: po_1=10, caller: <string>:1')
('scottbrian_utils.entry_trace', 10, "<string>:f1:? exit: return_value='po_1=10, '")
('test_scottbrian_utils.test_entry_trace', 10, "##################### arg_spec_ret_res.arg_spec='10'")
('scottbrian_utils.entry_trace', 10, "<string>:f1:? entry: po_1='...', caller: <string>:1")
('scottbrian_utils.entry_trace', 10, "<string>:f1:? exit: return_value='po_1=10, '")
('test_scottbrian_utils.test_entry_trace', 10, "##################### arg_spec_ret_res.arg_spec='10'")
('scottbrian_utils.entry_trace', 10, '<string>:f1:? entry: po_1=10, caller: <string>:1')
('scottbrian_utils.entry_trace', 10, "<string>:f1:? exit: return_value='po_1=10, '")
('test_scottbrian_utils.test_entry_trace', 10, "##################### arg_spec_ret_res.arg_spec=''")
('scottbrian_utils.entry_trace', 10, '<string>:f1:? entry: po_1=1, caller: <string>:1')
('scottbrian_utils.entry_trace', 10, "<string>:f1:? exit: return_value='po_1=1, '")
('test_scottbrian_utils.test_entry_trace', 10, "##################### arg_spec_ret_res.arg_spec='10'")
('scottbrian_utils.entry_trace', 10, "<string>:f1:? entry: po_1='...', caller: <string>:1")
('scottbrian_utils.entry_trace', 10, "<string>:f1:? exit: return_value='po_1=10, '")
('test_scottbrian_utils.test_entry_trace', 10, "##################### arg_spec_ret_res.arg_spec=''")
('scottbrian_utils.entry_trace', 10, "<string>:f1:? entry: po_1='...', caller: <string>:1")
('scottbrian_utils.entry_trace', 10, "<string>:f1:? exit: return_value='po_1=1, '")
"""
