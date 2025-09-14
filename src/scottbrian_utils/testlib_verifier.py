"""Module testlib_verifier.

==========
verify_lib
==========

The verify_lib function checks whether the code under test is from
the expected test library. For unit test, the source is normally tested
in place in the source library. For function test, however, the desired
method is to build the code using the project.toml and then test the
code from the build target library. When using tox to do the test, this
library is placed in the .tox folder. By default, verify_lib will
check that code comes from the library in the .tox folder by simply
searching for the string ".tox" in the file path for the library. The
library path is obtained using ''inspect.getsourcefile()'' for an
imported object passed in the call to verify_lib. Note that the
string to search for can also be specified in case some other test
library is used that does not have ".tox" in the path.

:Example1: pytest test case to ensure the correct library:

    .. code-block:: python

        from scottbrian_utils.testlib_verifier import verify_lib
        from scottbrian_utils.diag_msg import diag_msg
        import logging
        import os

        class TestDiagMsgCorrectLib:
            def test_diag_msg_correct_lib(self) -> None:
                if "TOX_ENV_NAME" in os.environ:
                    a_path = verify_lib(obj_to_check=diag_msg)

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
# verify_lib
########################################################################
def verify_lib(obj_to_check: Any, str_to_check: str = ".tox") -> str:

    logger.debug(f"verify_lib entered with: {obj_to_check=}, {str_to_check=}")

    src_file = inspect.getsourcefile(obj_to_check)
    if src_file is None:
        err_msg = f"verify_lib raising ObjNotFound: {obj_to_check=}"
        logger.debug(f"{err_msg}")
        raise ObjNotFound(err_msg)

    src_path = Path(src_file).as_posix()

    logger.debug(f"verify_lib found: {src_path=}")

    if str_to_check not in src_path:
        err_msg = f"verify_lib raising IncorrectSourceLibrary: {src_path=}"
        logger.debug(f"{err_msg}")
        raise IncorrectSourceLibrary(f"{err_msg}")

    return src_path
