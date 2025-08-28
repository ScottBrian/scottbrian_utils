"""test_src_verifier.py module."""

########################################################################
# Standard Library
########################################################################
import inspect
import logging
import os
import pytest
import re
import sys
from typing import Any, Callable, cast, NamedTuple, Optional, TypeVar

########################################################################
# Third Party
########################################################################


########################################################################
# Local
########################################################################
from scottbrian_utils.log_verifier import LogVer
from scottbrian_utils.src_verifier import (
    verify_source,
    IncorrectSourceLibrary,
    ObjNotFound,
)


########################################################################
# logger
########################################################################
logger = logging.getLogger(__name__)

########################################################################
# type aliases
########################################################################


########################################################################
# UniqueTS test exceptions
########################################################################
class ErrorTestSrcVerifier(Exception):
    """Base class for exception in this module."""

    pass


########################################################################
# TestUniqueTSExamples class
########################################################################
class TestSrcVerifierExamples:
    """Test examples of UniqueTS."""

    ####################################################################
    # test_exc_hook_example1
    ####################################################################
    def test_src_verifier_example1(self, capsys: Any) -> None:
        """Test unique time stamp example1.

        This example shows that obtaining two time stamps in quick
        succession using get_unique_time_ts() guarantees they will be
        unique.

        Args:
            capsys: pytest fixture to capture print output

        """
        print("mainline entered")

        print("mainline exiting")


########################################################################
# LocalDefClass
########################################################################
class LocalDefClass:
    """Class used to cause failure in verify_source call."""

    pass


########################################################################
# ExpPathArgs
########################################################################
class ExpPathArgs(NamedTuple):
    """NamedTuple for the expected path args."""

    str_to_check: str
    exp_src_path: str
    exp_log_pattern_args: str
    exp_log_pattern_found: str


########################################################################
# get_exp_src_path
########################################################################
def get_exp_src_path(
    obj_to_check: Any = verify_source, str_to_check: Optional[str] = None
) -> ExpPathArgs:
    """Return the expected source path."""

    if obj_to_check == LogVer:
        obj_to_check_str = "<class 'scottbrian_utils.log_verifier.LogVer'>"
        py_file_name = "log_verifier"
    else:
        obj_to_check_str = "<function verify_source at 0x[0-9A-F]+>"
        py_file_name = "src_verifier"

    if "TOX_ENV_NAME" in os.environ:
        str_to_check = ".tox" if str_to_check is None else str_to_check
        exp_src_path = (
            "C:/Users/Tiger/PycharmProjects/scottbrian_utils/"
            f".tox/py{sys.version_info.major}{sys.version_info.minor}"
            f"-(pytest|coverage)/Lib/site-packages/scottbrian_utils/{py_file_name}.py"
        )
    else:
        str_to_check = "src/scottbrian_utils/" if str_to_check is None else str_to_check
        if obj_to_check == LocalDefClass:
            file_str = "tests/test_scottbrian_utils/test_src_verifier/"
        else:
            file_str = "src/scottbrian_utils/"
        exp_src_path = (
            "C:/Users/Tiger/PycharmProjects/scottbrian_utils/"
            f"{file_str}{py_file_name}.py"
        )

    exp_log_pattern_args = (
        f"verify_source entered with: obj_to_check={obj_to_check_str}, "
        f"str_to_check='{str_to_check}'"
    )

    exp_log_pattern_found = f"verify_source found: src_path='{exp_src_path}'"

    return ExpPathArgs(
        str_to_check=str_to_check,
        exp_src_path=exp_src_path,
        exp_log_pattern_args=exp_log_pattern_args,
        exp_log_pattern_found=exp_log_pattern_found,
    )


########################################################################
# TestUniqueTSBasic class
########################################################################
class TestSrcVerifierBasic:
    """Test basic functions of UniqueTS."""

    ####################################################################
    # test_src_verifier_no_error_default
    ####################################################################
    @pytest.mark.parametrize("obj_to_check_arg", (verify_source, LogVer))
    def test_src_verifier_no_error_default(
        self, obj_to_check_arg: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test with default str_to_check."""

        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        exp_path_args: ExpPathArgs = get_exp_src_path(
            obj_to_check=obj_to_check_arg,
        )

        if exp_path_args.str_to_check == ".tox":
            # test default str_to_check
            actual_src_path = verify_source(obj_to_check=obj_to_check_arg)
        else:
            actual_src_path = verify_source(
                obj_to_check=obj_to_check_arg, str_to_check=exp_path_args.str_to_check
            )

        log_ver.add_pattern(
            exp_path_args.exp_log_pattern_args,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        log_ver.add_pattern(
            exp_path_args.exp_log_pattern_found,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        assert re.fullmatch(exp_path_args.exp_src_path, actual_src_path)

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_src_verifier_no_error_no_default
    ####################################################################
    @pytest.mark.parametrize("obj_to_check_arg", (verify_source, LogVer))
    def test_src_verifier_no_error_no_default(
        self, obj_to_check_arg: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test with str_to_check specified same as default."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        exp_path_args: ExpPathArgs = get_exp_src_path(obj_to_check=obj_to_check_arg)

        actual_src_path = verify_source(
            obj_to_check=obj_to_check_arg, str_to_check=exp_path_args.str_to_check
        )

        log_ver.add_pattern(
            exp_path_args.exp_log_pattern_args,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        log_ver.add_pattern(
            exp_path_args.exp_log_pattern_found,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        assert re.fullmatch(exp_path_args.exp_src_path, actual_src_path)

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_src_verifier_bad_str_to_check
    ####################################################################
    @pytest.mark.parametrize("obj_to_check_arg", (verify_source, LogVer))
    def test_src_verifier_bad_str_to_check(
        self, obj_to_check_arg: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test with str_to_check specified same as default."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        exp_path_args: ExpPathArgs = get_exp_src_path(
            obj_to_check=obj_to_check_arg,
            str_to_check="bad str_to_check",
        )
        exp_err_msg = (
            f"verify_source raising IncorrectSourceLibrary: "
            f"src_path='{exp_path_args.exp_src_path}'"
        )
        with pytest.raises(
            IncorrectSourceLibrary,
            match=exp_err_msg,
        ):
            verify_source(
                obj_to_check=obj_to_check_arg, str_to_check=exp_path_args.str_to_check
            )

        log_ver.add_pattern(
            exp_err_msg,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        log_ver.add_pattern(
            exp_path_args.exp_log_pattern_args,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        log_ver.add_pattern(
            exp_path_args.exp_log_pattern_found,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_src_verifier_local_obj_to_check
    ####################################################################
    def test_src_verifier_local_obj_to_check(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test with obj_to_check being locally defined."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        exp_src_path = (
            "C:/Users/Tiger/PycharmProjects/scottbrian_utils/"
            "tests/test_scottbrian_utils/test_src_verifier/test_src_verifier.py"
        )
        str_to_check = "tests/test_scottbrian_utils/test_src_verifier/test_src_verifier"

        obj_to_check_str = (
            "<class 'tests.test_scottbrian_utils."
            "test_src_verifier.test_src_verifier.LocalDefClass'>"
        )

        exp_log_pattern_args = (
            f"verify_source entered with: obj_to_check={obj_to_check_str}, "
            f"str_to_check='{str_to_check}'"
        )
        log_ver.add_pattern(
            exp_log_pattern_args,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        exp_log_pattern_found = f"verify_source found: src_path='{exp_src_path}'"

        log_ver.add_pattern(
            exp_log_pattern_found,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        actual_src_path = verify_source(
            obj_to_check=LocalDefClass, str_to_check=str_to_check
        )

        assert re.fullmatch(exp_src_path, actual_src_path)

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_src_verifier_local_obj_to_check
    ####################################################################
    def test_src_verifier_str_obj_to_check(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test with obj_to_check being locally defined."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        exp_log_pattern_args = (
            "verify_source entered with: obj_to_check='LocalDefClass', "
            "str_to_check='a string'"
        )
        log_ver.add_pattern(
            exp_log_pattern_args,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        with pytest.raises(
            TypeError,
            match=(
                "module, class, method, function, traceback, frame, or code object "
                "was expected, got str"
            ),
        ):
            verify_source(obj_to_check="LocalDefClass", str_to_check="a string")

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_src_verifier_unknown_obj_to_check
    ####################################################################
    def test_src_verifier_unknown_obj_to_check(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test with obj_to_check being unknown."""
        log_ver = LogVer(log_name=__name__)

        log_ver.test_msg("mainline entry")

        monkeypatch.setattr(
            inspect, "getsourcefile", lambda obj: None  # type: ignore[assignment]
        )

        exp_log_pattern_args = (
            "verify_source entered with: obj_to_check='UnknownFunction', "
            "str_to_check='a string'"
        )
        log_ver.add_pattern(
            exp_log_pattern_args,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        exp_err_msg = (
            "verify_source raising ObjNotFound: obj_to_check='UnknownFunction'"
        )
        with pytest.raises(ObjNotFound, match=exp_err_msg):
            verify_source(obj_to_check="UnknownFunction", str_to_check="a string")

        log_ver.add_pattern(
            exp_err_msg,
            log_name="scottbrian_utils.src_verifier",
            fullmatch=True,
        )

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)
