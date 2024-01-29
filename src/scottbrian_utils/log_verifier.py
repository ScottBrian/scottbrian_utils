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
from dataclasses import dataclass
import logging
import pytest
import re
from typing import Any, Optional, Type, TYPE_CHECKING, Union

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################
from scottbrian_utils.flower_box import print_flower_box_msg

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
        self.expected_messages: list[tuple[str, int, Any]] = []
        self.expected_messages_fullmatch: list[tuple[str, int, Any]] = []
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
            self.expected_messages_fullmatch.append(
                (log_name_to_use, log_level, re.compile(log_msg))
            )
        else:
            self.expected_messages.append(
                (log_name_to_use, log_level, re.compile(log_msg))
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
        # make a work copy of fullmatch expected records
        unmatched_exp_records_fullmatch: list[
            tuple[str, int, Any]
        ] = self.expected_messages_fullmatch.copy()

        # make a work copy of expected records
        unmatched_exp_records: list[
            tuple[str, int, Any]
        ] = self.expected_messages.copy()

        # make a work copy of actual records
        unmatched_actual_records: list[
            tuple[str, int, Any]
        ] = caplog.record_tuples.copy()

        matched_records: list[tuple[str, int, Any]] = []

        ################################################################
        # find matches, update working copies to reflect results
        ################################################################
        if unmatched_exp_records_fullmatch:  # if fullmatch records
            for actual_record in caplog.record_tuples:
                # look for fullmatch
                for idx, exp_record in enumerate(unmatched_exp_records_fullmatch):
                    # check that the logger name, level, and message
                    # match
                    if (
                        exp_record[0] == actual_record[0]
                        and exp_record[1] == actual_record[1]
                        and exp_record[2].fullmatch(actual_record[2])
                    ):
                        unmatched_exp_records_fullmatch.pop(idx)
                        unmatched_actual_records.remove(actual_record)
                        matched_records.append(
                            (actual_record[0], actual_record[1], actual_record[2])
                        )
                        break

        if unmatched_exp_records:  # if partial match records
            for actual_record in unmatched_actual_records.copy():
                # look for partial match in unmatched_exp_records
                for idx, exp_record in enumerate(unmatched_exp_records):
                    # check that the logger name, level, and message
                    # match
                    if (
                        exp_record[0] == actual_record[0]
                        and exp_record[1] == actual_record[1]
                        and exp_record[2].match(actual_record[2])
                    ):
                        unmatched_exp_records.pop(idx)
                        unmatched_actual_records.remove(actual_record)
                        matched_records.append(
                            (actual_record[0], actual_record[1], actual_record[2])
                        )
                        break

        # convert unmatched expected records to string form
        unmatched_exp_records_2 = []
        for item in unmatched_exp_records_fullmatch:
            unmatched_exp_records_2.append((item[0], item[1], item[2].pattern))

        for item in unmatched_exp_records:
            unmatched_exp_records_2.append((item[0], item[1], item[2].pattern))

        return MatchResults(
            num_exp_records=(
                len(self.expected_messages) + len(self.expected_messages_fullmatch)
            ),
            num_exp_unmatched=len(unmatched_exp_records_2),
            num_actual_records=len(caplog.records),
            num_actual_unmatched=len(unmatched_actual_records),
            num_records_matched=len(matched_records),
            unmatched_exp_records=unmatched_exp_records_2,
            unmatched_actual_records=unmatched_actual_records,
            matched_records=matched_records,
        )

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
