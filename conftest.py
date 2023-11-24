from doctest import ELLIPSIS
from doctest import OutputChecker as BaseOutputChecker

import re

from sybil import Sybil
from sybil.parsers.rest import PythonCodeBlockParser

from scottbrian_utils.time_hdr import get_datetime_match_string
from scottbrian_utils.doc_checker import DocCheckerTestParser

from typing import Any


class SbtDocCheckerOutputChecker(BaseOutputChecker):
    def __init__(self) -> None:
        """Initialize the output checker object."""
        self.mod_name: str = ""
        self.msgs: list[str] = []

    def check_output(self, want: str, got: str, optionflags: int) -> bool:
        """Check the output of the example against expected value.

        Args:
            want: the expected value of the example output
            got: the actual value of the example output
            optionflags: doctest option flags for the Sybil
                BaseOutPutChecker check_output method
        Returns:
            True if the want and got values match, False otherwise
        """
        old_want = want
        old_got = got

        def repl_dt(match_obj: Any) -> str:
            return found_items.__next__().group()

        if self.mod_name == 'time_hdr' or self.mod_name == 'README':
            # find the actual occurrences and replace in want
            for time_hdr_dt_format in ["%a %b %d %Y %H:%M:%S",
                                       "%m/%d/%y %H:%M:%S"]:
                match_str = get_datetime_match_string(time_hdr_dt_format)

                match_re = re.compile(match_str)
                found_items = match_re.finditer(got)
                want = match_re.sub(repl_dt, want)

            # replace elapsed time in both want and got
            match_str = 'Elapsed time: 0:00:00.[0-9| ]{6,6}'
            replacement = 'Elapsed time: 0:00:00       '
            want = re.sub(match_str, replacement, want)
            got = re.sub(match_str, replacement, got)

        if self.mod_name == 'file_catalog' or self.mod_name == 'README':
            match_str = r'\\'
            replacement = '/'
            got = re.sub(match_str, replacement, got)

            match_str = '//'
            replacement = '/'
            got = re.sub(match_str, replacement, got)

        if self.mod_name == 'diag_msg' or self.mod_name == 'README':
            for diag_msg_dt_fmt in ["%H:%M:%S.%f", "%a %b-%d %H:%M:%S"]:
                match_str = get_datetime_match_string(diag_msg_dt_fmt)

                match_re = re.compile(match_str)
                found_items = match_re.finditer(got)
                want = match_re.sub(repl_dt, want)

            # match_str = "<.+?>"
            if self.mod_name == 'diag_msg':
                match_str = "diag_msg.py\[0\]>"
            else:
                match_str = "README.rst\[0\]>"
            replacement = '<input>'
            got = re.sub(match_str, replacement, got)

        if self.mod_name == 'pauser':
            match_str = 'pauser.min_interval_secs=0.0[0-9]{1,2}'

            found_item = re.match(match_str, got)
            if found_item:
                want = re.sub(match_str, found_item.group(), want)

            match_str = ('metrics.pause_ratio=1.0, '
                         'metrics.sleep_ratio=0.[0-9]+')

            found_item = re.match(match_str, got)
            if found_item:
                want = re.sub(match_str, found_item.group(), want)

        self.msgs.append([old_want, want, old_got, got])
        return BaseOutputChecker.check_output(self, want, got, optionflags)


pytest_collect_file = Sybil(
    parsers=[
        DocCheckerTestParser(optionflags=ELLIPSIS,
                             doc_checker_output_checker=SbtDocCheckerOutputChecker()
                             ),
        PythonCodeBlockParser(),],
    patterns=['*.rst', '*.py'],
    # excludes=['log_verifier.py']
    ).pytest()
