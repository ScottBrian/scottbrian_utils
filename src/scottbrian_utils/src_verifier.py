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

    from scottbrian_utils.src_verifier import verify_source
    from scottbrian_utils.diag_msg import diag_msg
    import logging

    class TestDiagMsgCorrectSource:
        def test_diag_msg_correct_source(self) -> None:
            if "TOX_ENV_NAME" in os.environ:
                verify_source(obj_to_check=diag_msg)


"""

########################################################################
# Standard Library
########################################################################
import inspect
import logging
from pathlib import Path
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


class ObjNotFound(ErrorSrcVer):
    """ObjNotFound exception class."""

    pass


class IncorrectSourceLibrary(ErrorSrcVer):
    """IncorrectSourceLibrary exception class."""

    pass


########################################################################
# verify_source
########################################################################
def verify_source(obj_to_check: Any, str_to_check: str = ".tox") -> str:

    logger.debug(f"verify_source entered with: {obj_to_check=}, {str_to_check=}")

    src_file = inspect.getsourcefile(obj_to_check)
    if src_file is None:
        err_msg = f"verify_source raising ObjNotFound: {obj_to_check=}"
        logger.debug(f"{err_msg}")
        raise ObjNotFound(err_msg)

    src_path = Path(src_file).as_posix()

    logger.debug(f"verify_source found: {src_path=}")

    if str_to_check not in src_path:
        err_msg = f"verify_source raising IncorrectSourceLibrary: {src_path=}"
        logger.debug(f"{err_msg}")
        raise IncorrectSourceLibrary(f"{err_msg}")

    return src_path
