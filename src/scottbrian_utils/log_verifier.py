"""Module log_verifier.

======
LogVer
======

The LogVer class is intended to be used during testing to allow a
test case to specify expected log messages and then verify that they
have been issued.

:Example1: log a message and verify

>>> from scottbrian_utils.log_verifier import LogVer
>>> import logging
>>> logger = logging.getLogger(__name__)
>>> log_ver = LogVer()
>>> log_msg = 'hello'
>>> log_ver.add_msg(log_msg=log_msg)
>>> logger.debug(log_msg)
>>> log_ver.get_match_results()
>>> log_ver.print_match_results()
>>> log_ver.verify_log_results()
<BLANKLINE>
**********************************
* number expected log records: 1 *
* number expected unmatched  : 0 *
* number actual log records  : 1 *
* number actual unmatched    : 0 *
* number of matched records  : 1 *
**********************************
<BLANKLINE>
******************************
* unmatched expected records *
******************************
<BLANKLINE>
****************************
* unmatched actual records *
****************************
<BLANKLINE>
***********************
* matched log records *
***********************
hello


:Example2: expect two log records, only one was issued

>>> from scottbrian_utils.log_verifier import LogVer
>>> import logging
>>> logger = logging.getLogger(__name__)
>>> log_ver = LogVer()
>>> log_msg1 = 'hello'
>>> log_ver.add_msg(log_msg=log_msg1)
>>> log_msg2 = 'goodbye'
>>> log_ver.add_msg(log_msg=log_msg2)
>>> logger.debug(log_msg1)
>>> log_ver.get_match_results()
>>> log_ver.print_match_results()
<BLANKLINE>
**********************************
* number expected log records: 2 *
* number expected unmatched  : 1 *
* number actual log records  : 1 *
* number actual unmatched    : 0 *
* number of matched records  : 1 *
**********************************
<BLANKLINE>
******************************
* unmatched expected records *
******************************
goodbye
<BLANKLINE>
****************************
* unmatched actual records *
****************************
<BLANKLINE>
***********************
* matched log records *
***********************
hello


:Example3: expect one log record, two were issued

>>> from scottbrian_utils.log_verifier import LogVer
>>> import logging
>>> logger = logging.getLogger(__name__)
>>> log_ver = LogVer()
>>> log_msg1 = 'hello'
>>> log_ver.add_msg(log_msg=log_msg1)
>>> log_msg2 = 'goodbye'
>>> logger.debug(log_msg1)
>>> logger.debug(log_msg2)
>>> log_ver.get_match_results()
>>> log_ver.print_match_results()
<BLANKLINE>
**********************************
* number expected log records: 1 *
* number expected unmatched  : 0 *
* number actual log records  : 2 *
* number actual unmatched    : 1 *
* number of matched records  : 1 *
**********************************
<BLANKLINE>
******************************
* unmatched expected records *
******************************
<BLANKLINE>
****************************
* unmatched actual records *
****************************
goodbye
<BLANKLINE>
***********************
* matched log records *
***********************
hello


:Example4: expect two log records, two were issued, one different

>>> from scottbrian_utils.log_verifier import LogVer
>>> import logging
>>> logger = logging.getLogger(__name__)
>>> log_ver = LogVer()
>>> log_msg1 = 'hello'
>>> log_ver.add_msg(log_msg=log_msg1)
>>> log_msg2a = 'goodbye'
>>> log_ver.add_msg(log_msg=log_msg2a)
>>> log_msg2b = 'see you soon'
>>> logger.debug(log_msg1)
>>> logger.debug(log_msg2b)
>>> log_ver.get_match_results()
>>> log_ver.print_match_results()
<BLANKLINE>
**********************************
* number expected log records: 2 *
* number expected unmatched  : 1 *
* number actual log records  : 2 *
* number actual unmatched    : 1 *
* number of matched records  : 1 *
**********************************
<BLANKLINE>
******************************
* unmatched expected records *
******************************
goodbye
<BLANKLINE>
****************************
* unmatched actual records *
****************************
see you soon
<BLANKLINE>
***********************
* matched log records *
***********************
hello


The log_verifier module contains:

    1) LogVer class with methods:

       a. add_call_seq
       b. get_call_seq
       c. add_msg
       d. verify_log_msgs

"""

########################################################################
# Standard Library
########################################################################
from dataclasses import dataclass
import re
from typing import Any, Optional, Union

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


class IncorrectNumberOfMatchedMessages(LogVerError):
    """Number of matched expected messages not equal to actual."""
    pass


class NonZeroNumberOfMatchedMessages(LogVerError):
    """Number of matched expected messages not equal to zero."""
    pass


@dataclass
class MatchResults:
    num_exp_records: int
    num_exp_unmatched: int
    num_actual_records: int
    num_actual_unmatched: int
    num_records_matched: int
    unmatched_exp_records: list[str]
    unmatched_actual_records: list[str]
    matched_records: list[str]


########################################################################
# LogVer class
########################################################################
class LogVer:
    """Log Message Verification Class."""

    ####################################################################
    # __init__
    ####################################################################
    def __init__(self) -> None:
        """Initialize object."""
        self.call_seqs = {}
        self.expected_messages = []

    ####################################################################
    # add_call_seq
    ####################################################################
    def add_call_seq(self,
                     name: str,
                     seq: str) -> None:
        """Add a call sequence for a given name.

        Args:
            name: name for whom the call sequence represents
            seq: the call sequence in a format as described by
                   get_formatted_call_sequence in diag_msg.py

        """
        self.call_seqs[name] = seq

    ####################################################################
    # add_call_seq
    ####################################################################
    def get_call_seq(self,
                     name: str) -> str:
        """Retrieve a call sequence by name.

        Args:
            name: name for whom the call sequence represents

        Returns:
            the call sequence in a format as described by
              get_formatted_call_sequence in diag_msg.py with the regex
              string ":[0-9]*" appended to represent the source line
              number to match

        """
        return self.call_seqs[name] + ':[0-9]* '

    ####################################################################
    # add_msg
    ####################################################################
    def add_msg(self, log_msg: str) -> None:
        """Add a message to the expected log messages.

        Args:
            log_msg: message to add

        """
        self.expected_messages.append(re.compile(log_msg))

    ###########################################################################
    # get_match_results
    ###########################################################################
    def get_match_results(self,
                          caplog: Any) -> MatchResults:
        """Match the expected to actual log records.

        Args:
            caplog: pytest fixture that captures log messages

        Returns:
            Number of expected records, number of actual records,
              number of matching records, list of unmatched expected
              records, list of unmatched actual records, and list
              or matching records

        """
        unmatched_exp_records = []
        unmatched_actual_records = []
        matched_records = []

        # make a work copy of expected records
        for record in self.expected_messages:
            unmatched_exp_records.append(record)

        # make a work copy of actual records
        for record in caplog.records:
            unmatched_actual_records.append(record.msg)

        # find matches, update working copies to reflect results
        for actual_record in enumerate(caplog.record_tuples):
            for idx, exp_record in enumerate(unmatched_exp_records):
                if exp_record.match(actual_record[1][2]):
                    unmatched_exp_records.pop(idx)
                    unmatched_actual_records.remove(actual_record[1][2])
                    matched_records.append(actual_record[1][2])
                    break

        # convert unmatched expected records to string form
        unmatched_exp_records_2 = []
        for re_item in unmatched_exp_records:
            unmatched_exp_records_2.append(re_item.pattern)

        return MatchResults(num_exp_records=len(self.expected_messages),
                            num_exp_unmatched=len(unmatched_exp_records_2),
                            num_actual_records=len(caplog.records),
                            num_actual_unmatched=len(unmatched_actual_records),
                            num_records_matched=len(matched_records),
                            unmatched_exp_records=unmatched_exp_records_2,
                            unmatched_actual_records=unmatched_actual_records,
                            matched_records=matched_records)

    ###########################################################################
    # print_match_results
    ###########################################################################
    def print_match_results(self,
                            match_results: MatchResults) -> None:
        """Print the match results.

        Args:
            match_results: contains the results to be printed

        """
        max_num = max(match_results.num_exp_records,
                      match_results.num_exp_unmatched,
                      match_results.num_actual_records,
                      match_results.num_actual_unmatched,
                      match_results.num_records_matched)
        max_len = len(str(max_num))
        msg1 = ('number expected log records: '
                f'{match_results.num_exp_records:>{max_len}}')
        msg2 = ('number expected unmatched  : '
                f'{match_results.num_exp_unmatched:>{max_len}}')
        msg3 = ('number actual log records  : '
                f'{match_results.num_actual_records:>{max_len}}')
        msg4 = ('number actual unmatched    : '
                f'{match_results.num_actual_unmatched:>{max_len}}')
        msg5 = ('number matched records     : '
                f'{match_results.num_records_matched:>{max_len}}')

        print_flower_box_msg([msg1, msg2, msg3, msg4, msg5])

        print_flower_box_msg('unmatched expected records')
        for log_msg in match_results.unmatched_exp_records:
            print(log_msg)

        print_flower_box_msg('unmatched actual records')
        for log_msg in match_results.unmatched_actual_records:
            print(log_msg)

        print_flower_box_msg('matched log records')
        for log_msg in match_results.matched_records:
            print(log_msg)

    ###########################################################################
    # verify log messages
    ###########################################################################
    def verify_log_results(self,
                           match_results: MatchResults,
                           log_enabled_tf: bool = True) -> None:
        """Verify that each log message issued is as expected.

        Args:
            match_results: contains the results to be verified
            log_enabled_tf: indicated whether log is enabled

        Raises:
            UnmatchedExpectedMessages: There are expected log messages
                that failed to match actual log messages.
            UnmatchedActualMessages: There are actual log messages that
                failed to match expected log messages.
            IncorrectNumberOfMatchedMessages: The number of expected log
                messages that were matched is not equal to the number of
                actual log messages.
            NonZeroNumberOfMatchedMessages: The number of expected log
                messages that were matched is not equal to zero when
                logging was not enabled

        """
        if log_enabled_tf:
            if match_results.num_exp_unmatched:
                raise UnmatchedExpectedMessages(
                    f'There are {match_results.num_exp_unmatched} '
                    'expected log messages that failed to match actual log '
                    'messages.')

            if match_results.num_actual_unmatched:
                raise UnmatchedActualMessages(
                    f'There are {match_results.num_actual_unmatched} '
                    'actual log messages that failed to match expected log '
                    'messages.')

            if (match_results.num_records_matched
                    != match_results.num_actual_records):
                raise IncorrectNumberOfMatchedMessages(
                    'The number of expected log messages that were matched '
                    f'({match_results.num_records_matched}) is not equal to '
                    'the number of actual log messages '
                    f'({match_results.num_actual_records})'
                )
        else:
            if match_results.num_records_matched:
                raise NonZeroNumberOfMatchedMessages(
                    'The number of expected log messages that were matched '
                    f'({match_results.num_records_matched}) is not equal to '
                    'zero when logging was not enabled'
                )
