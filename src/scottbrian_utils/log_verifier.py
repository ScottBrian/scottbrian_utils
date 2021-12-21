"""Module log_verifier.

======
LogVer
======

The LogVer class is intended to be used during testing to allow a
test case to specify expected log messages and then verify that they
have been issued.

:Example: log a message and verify

>>> from scottbrian_utils.log_verifier import LogVer
>>> import logging
>>> logger = logging.getLogger(__name__)
>>> log_ver = LogVer()
>>> log_msg = 'hello'
>>> log_ver.add_msg(log_msg=log_msg)
>>> logger.debug(log_msg)
>>> log_ver.verify_log_msgs()
<BLANKLINE>
num_log_records_found: 1 of 1
******** matched log records found ********
hello
******** remaining unmatched log records ********
******** remaining expected log records ********


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
import re
from typing import Any, Optional, Union

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################

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


class GetMsgTimedOut(LogVerError):
    """LogVer get_msg timed out waiting for msg."""
    pass


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
        self.call_seqs[name] = seq + ':[0-9]* '

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
        return self.call_seqs[name]

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
    # verify log messages
    ###########################################################################
    def verify_log_msgs(self,
                        caplog: Any,
                        log_enabled_tf: bool = True) -> None:
        """Verify that each log message issued is as expected.

        Args:
            caplog: pytest fixture that captures log messages
            log_enabled_tf: indicated whether log is enabled

        """
        num_log_records_found = 0
        log_records_found = []
        caplog_recs = []
        for record in caplog.records:
            caplog_recs.append(record.msg)

        for idx, record in enumerate(caplog.records):
            # print(record.msg)
            # print(self.exp_log_msg)
            for idx2, l_msg in enumerate(self.expected_messages):
                if l_msg.match(record.msg):
                    # print(l_msg.match(record.msg))
                    self.expected_messages.pop(idx2)
                    caplog_recs.remove(record.msg)
                    log_records_found.append(record.msg)
                    num_log_records_found += 1
                    break

        print(f'\nnum_log_records_found: '
              f'{num_log_records_found} of {len(caplog.records)}')

        print(('*' * 8) + ' matched log records found ' + ('*' * 8))
        for log_msg in log_records_found:
            print(log_msg)

        print(('*' * 8) + ' remaining unmatched log records ' + ('*' * 8))
        for log_msg in caplog_recs:
            print(log_msg)

        print(('*' * 8) + ' remaining expected log records ' + ('*' * 8))
        for exp_lm in self.expected_messages:
            print(exp_lm)

        if log_enabled_tf:
            assert not self.expected_messages
            assert num_log_records_found == len(caplog.records)
        else:
            assert self.expected_messages
            assert num_log_records_found == 0
