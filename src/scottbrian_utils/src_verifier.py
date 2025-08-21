"""Module src_verifier.

======
SrcVer
======

The src_verifier module contains a function that checks whether the
source under test resides in the expected test library. This ensures the
code was properly built and is not being tested in place in the source
library.

:Example1: pytest test case to ensure the correct source:

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
"""

########################################################################
# Standard Library
########################################################################
import inspect
import logging
from pathlib import Path
import re
from typing import Any

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################

########################################################################
# logger
########################################################################
logger = logging.getLogger(__name__)


########################################################################
# src_verifier exceptions
########################################################################
class ErrorSrcVer(Exception):
    """Base class for exception in this module."""

    pass


class IncorrectSourceLibrary(ErrorSrcVer):
    """IncorrectSourceLibrary exception class."""

    pass


########################################################################
# verify_source
########################################################################
def verify_source(obj_to_check: Any, str_to_check: str = ".tox") -> str:

    logger.debug(f"verify_source entered with: {obj_to_check=}, {str_to_check=}")

    src_path = Path(inspect.getsourcefile(obj_to_check)).as_posix()

    logger.debug(f"verify_source found: {src_path=}")

    if str_to_check not in src_path:
        raise IncorrectSourceLibrary(f"Incorrect source library: {src_path}")

    return src_path
