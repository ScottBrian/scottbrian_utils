"""test_diag_msg.py module."""

########################################################################
# Standard Library
########################################################################
from datetime import datetime
import logging
import os

# noinspection PyProtectedMember
from sys import _getframe
import sys  # noqa: F401

from typing import Any, cast, Deque, Final, List, NamedTuple, Optional, Union

########################################################################
# Third Party
########################################################################
import pytest
from collections import deque

########################################################################
# Local
########################################################################
from scottbrian_utils.diag_msg import get_caller_info
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.diag_msg import diag_msg
from scottbrian_utils.diag_msg import CallerInfo
from scottbrian_utils.diag_msg import diag_msg_datetime_fmt
from scottbrian_utils.diag_msg import get_formatted_call_seq_depth
from scottbrian_utils.diag_msg import diag_msg_caller_depth

from scottbrian_utils.src_verifier import verify_source

from scottbrian_utils.entry_trace import etrace

logger = logging.getLogger(__name__)


########################################################################
# DiagMsgArgs NamedTuple
########################################################################
class DiagMsgArgs(NamedTuple):
    """Structure for the testing of various args for diag_msg."""

    arg_bits: int
    dt_format_arg: str
    depth_arg: int
    msg_arg: List[Union[str, int]]
    file_arg: str


########################################################################
# depth_arg fixture
########################################################################
depth_arg_list = [None, 0, 1, 2, 3]


@pytest.fixture(params=depth_arg_list)
def depth_arg(request: Any) -> int:
    """Using different depth args.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# file_arg fixture
########################################################################
file_arg_list = [None, "sys.stdout", "sys.stderr"]


@pytest.fixture(params=file_arg_list)
def file_arg(request: Any) -> str:
    """Using different file arg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(str, request.param)


########################################################################
# latest_arg fixture
########################################################################
latest_arg_list = [None, 0, 1, 2, 3]


@pytest.fixture(params=latest_arg_list)
def latest_arg(request: Any) -> Union[int, None]:
    """Using different depth args.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# msg_arg fixture
########################################################################
msg_arg_list = [
    [None],
    ["one-word"],
    ["two words"],
    ["three + four"],
    ["two", "items"],
    ["three", "items", "for you"],
    ["this", "has", "number", 4],
    ["here", "some", "math", 4 + 1],
]


@pytest.fixture(params=msg_arg_list)
def msg_arg(request: Any) -> List[str]:
    """Using different message arg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(List[str], request.param)


########################################################################
# seq_slice is used to get a contiguous section of the sequence string
# which is needed to verify get_formatted_call_seq invocations where
# latest is non-zero or depth is beyond our known call sequence (i.e.,
# the call seq string has system functions prior to calling the test
# case)
########################################################################
def seq_slice(call_seq: str, start: int = 0, end: Optional[int] = None) -> str:
    """Return a reduced depth call sequence string.

    Args:
        call_seq: The call sequence string to slice
        start: Species the latest entry to return with zero being the
                 most recent
        end: Specifies one entry earlier than the earliest entry to
               return

    Returns:
          A slice of the input call sequence string
    """
    seq_items = call_seq.split(" -> ")

    # Note that we allow start and end to both be zero, in which case an
    # empty sequence is returned. Also note that the sequence is earlier
    # calls to later calls from left to right, so a start of zero means
    # the end of the sequence (the right most entry) and the end is the
    # depth, meaning how far to go left toward earlier entries. The
    # following code reverses the meaning of start and end so that we
    # can slice the sequence without having to first reverse it.

    adj_end = len(seq_items) - start
    assert 0 <= adj_end  # ensure not beyond number of items

    adj_start = 0 if end is None else len(seq_items) - end
    assert 0 <= adj_start  # ensure not beyond number of items

    ret_seq = ""
    arrow = " -> "
    for i in range(adj_start, adj_end):
        if i == adj_end - 1:  # if last item
            arrow = ""
        ret_seq = f"{ret_seq}{seq_items[i]}{arrow}"

    return ret_seq


########################################################################
# get_exp_seq is a helper function used by many test cases
########################################################################
def get_exp_seq(
    exp_stack: Deque[CallerInfo], latest: int = 0, depth: Optional[int] = None
) -> str:
    """Return the expected call sequence string based on the exp_stack.

    Args:
        exp_stack: The expected stack as modified by each test case
        depth: The number of entries to build
        latest: Specifies where to start in the seq for the most recent
                  entry

    Returns:
          The call string that get_formatted_call_sequence is expected
           to return
    """
    if depth is None:
        depth = len(exp_stack) - latest
    exp_seq = ""
    arrow = ""
    for i, exp_info in enumerate(reversed(exp_stack)):
        if i < latest:
            continue
        if i == latest + depth:
            break
        if exp_info.func_name:
            dbl_colon = "::"
        else:
            dbl_colon = ""
        if exp_info.cls_name:
            dot = "."
        else:
            dot = ""

        # # import inspect
        # print('exp_info.line_num:', i, ':', exp_info.line_num)
        # for j in range(5):
        #     frame = _getframe(j)
        #     print(frame.f_code.co_name, ':', frame.f_lineno)

        exp_seq = (
            f"{exp_info.mod_name}{dbl_colon}"
            f"{exp_info.cls_name}{dot}{exp_info.func_name}:"
            f"{exp_info.line_num}{arrow}{exp_seq}"
        )
        arrow = " -> "

    return exp_seq


########################################################################
# verify_diag_msg is a helper function used by many test cases
########################################################################
@etrace(omit_parms=("exp_stack", "capsys"))
def verify_diag_msg(
    exp_stack: Deque[CallerInfo],
    before_time: datetime,
    after_time: datetime,
    capsys: pytest.CaptureFixture[str],
    diag_msg_args: DiagMsgArgs,
) -> None:
    """Verify the captured msg is as expected.

    Args:
        exp_stack: The expected stack of callers
        before_time: The time just before issuing the diag_msg
        after_time: The time just after the diag_msg
        capsys: Pytest fixture that captures output
        diag_msg_args: Specifies the args used on the diag_msg
                         invocation

    """
    # We are about to format the before and after times to match the
    # precision of the diag_msg time. In doing so, we may end up with
    # the after time appearing to be earlier than the before time if the
    # times are very close to 23:59:59 and the format does not include
    # the date information (e.g., before_time ends up being
    # 23:59:59.999938 and after_time end up being 00:00:00.165). If this
    # happens, we can't reliably check the diag_msg time so we will
    # simply skip the check. The following assert proves only that the
    # times passed in are good to start with before we strip off any
    # resolution.
    # Note: changed the following from 'less than' to
    # 'less than or equal' because the times are apparently the
    # same on a faster machine (meaning the resolution of microseconds
    # is not enough)

    if not before_time <= after_time:
        logger.debug(f"check 1: {before_time=}, {after_time=}")
    assert before_time <= after_time

    before_time_year = before_time.year
    after_time_year = after_time.year

    year_straddle: bool = False
    if before_time_year < after_time_year:
        year_straddle = True

    day_straddle: bool = False
    if before_time.toordinal() < after_time.toordinal():
        day_straddle = True

    dt_format_to_use = diag_msg_args.dt_format_arg
    add_year: bool = False
    if (
        "%y" not in dt_format_to_use
        and "%Y" not in dt_format_to_use
        and "%d" in dt_format_to_use
    ):
        dt_format_to_use = f"{'%Y'} {dt_format_to_use}"
        add_year = True

    before_time = datetime.strptime(
        before_time.strftime(dt_format_to_use), dt_format_to_use
    )
    after_time = datetime.strptime(
        after_time.strftime(dt_format_to_use), dt_format_to_use
    )

    if diag_msg_args.file_arg == "sys.stdout":
        cap_msg = capsys.readouterr().out
    else:  # must be stderr
        cap_msg = capsys.readouterr().err

    str_list = cap_msg.split()
    dt_format_split_list = dt_format_to_use.split()

    msg_time_str = ""
    if add_year:
        str_list = [str(before_time_year)] + str_list
    for i in range(len(dt_format_split_list)):
        msg_time_str = f"{msg_time_str}{str_list.pop(0)} "
    msg_time_str = msg_time_str.rstrip()
    msg_time = datetime.strptime(msg_time_str, dt_format_to_use)

    # if safe to proceed with low resolution
    if before_time <= after_time and not year_straddle and not day_straddle:
        if not before_time <= msg_time <= after_time:
            logger.debug(f"check 2: {before_time=}, {msg_time=}, {after_time=}")
        assert before_time <= msg_time <= after_time

    # build the expected call sequence string
    call_seq = ""
    for i in range(len(str_list)):
        word = str_list.pop(0)
        if i % 2 == 0:  # if even
            if ":" in word:  # if this is a call entry
                call_seq = f"{call_seq}{word}"
            else:  # not a call entry, must be first word of msg
                str_list.insert(0, word)  # put it back
                break  # we are done
        elif word == "->":  # odd and we have arrow
            call_seq = f"{call_seq} {word} "
        else:  # odd and no arrow (beyond call sequence)
            str_list.insert(0, word)  # put it back
            break  # we are done

    verify_call_seq(
        exp_stack=exp_stack, call_seq=call_seq, seq_depth=diag_msg_args.depth_arg
    )

    captured_msg = ""
    for i in range(len(str_list)):
        captured_msg = f"{captured_msg}{str_list[i]} "
    captured_msg = captured_msg.rstrip()

    check_msg = ""
    for i in range(len(diag_msg_args.msg_arg)):
        check_msg = f"{check_msg}{diag_msg_args.msg_arg[i]} "
    check_msg = check_msg.rstrip()

    if not captured_msg == check_msg:
        logger.debug(f"check 3: {before_time=}, {msg_time=}, {after_time=}")
    assert captured_msg == check_msg


########################################################################
# verify_call_seq is a helper function used by many test cases
########################################################################
def verify_call_seq(
    exp_stack: Deque[CallerInfo],
    call_seq: str,
    seq_latest: Optional[int] = None,
    seq_depth: Optional[int] = None,
) -> None:
    """Verify the captured msg is as expected.

    Args:
        exp_stack: The expected stack of callers
        call_seq: The call sequence from get_formatted_call_seq or from
                    diag_msg to check
        seq_latest: The value used for the get_formatted_call_seq latest
                      arg
        seq_depth: The value used for the get_formatted_call_seq depth
                     arg

    """
    # Note on call_seq_depth and exp_stack_depth: We need to test that
    # get_formatted_call_seq and diag_msg will correctly return the
    # entries on the real stack to the requested depth. The test cases
    # involve calling a sequence of functions so that we can grow the
    # stack with known entries and thus be able to verify them. The real
    # stack will also have entries for the system code prior to giving
    # control to the first test case. We need to be able to test the
    # depth specification on the get_formatted_call_seq and diag_msg,
    # and this may cause the call sequence to contain entries for the
    # system. The call_seq_depth is used to tell the verification code
    # to limit the check to the entries we know about and not the system
    # entries. The exp_stack_depth is also needed when we know we have
    # limited the get_formatted_call_seq or diag_msg in which case we
    # can't use the entire exp_stack.
    #
    # In the following table, the exp_stack depth is the number of
    # functions called, the get_formatted_call_seq latest and depth are
    # the values specified for the get_formatted_call_sequence latest
    # and depth args. The seq_slice latest and depth are the values to
    # use for the slice (remembering that the call_seq passed to
    # verify_call_seq may already be a slice of the real stack). Note
    # that values of 0 and None for latest and depth, respectively, mean
    # slicing in not needed. The get_exp_seq latest and depth specify
    # the slice of the exp_stack to use. Values of 0 and None here mean
    # no slicing is needed. Note also that from both seq_slice and
    # get_exp_seq, None for the depth arg means to return all of the
    # remaining entries after any latest slicing is done. Also, a
    # value of no-test means that verify_call_seq can not do a
    # verification since the call_seq is not  in the range of the
    # exp_stack.

    # gfcs = get_formatted_call_seq
    #
    # exp_stk | gfcs           | seq_slice         | get_exp_seq
    # depth   | latest | depth | start   |     end | latest  | depth
    # ------------------------------------------------------------------
    #       1 |      0       1 |       0 | None (1) |      0 | None (1)
    #       1 |      0       2 |       0 |       1  |      0 | None (1)
    #       1 |      0       3 |       0 |       1  |      0 | None (1)
    #       1 |      1       1 |            no-test |     no-test
    #       1 |      1       2 |            no-test |     no-test
    #       1 |      1       3 |            no-test |     no-test
    #       1 |      2       1 |            no-test |     no-test
    #       1 |      2       2 |            no-test |     no-test
    #       1 |      2       3 |            no-test |     no-test
    #       2 |      0       1 |       0 | None (1) |      0 |       1
    #       2 |      0       2 |       0 | None (2) |      0 | None (2)
    #       2 |      0       3 |       0 |       2  |      0 | None (2)
    #       2 |      1       1 |       0 | None (1) |      1 | None (1)
    #       2 |      1       2 |       0 |       1  |      1 | None (1)
    #       2 |      1       3 |       0 |       1  |      1 | None (1)
    #       2 |      2       1 |            no-test |     no-test
    #       2 |      2       2 |            no-test |     no-test
    #       2 |      2       3 |            no-test |     no-test
    #       3 |      0       1 |       0 | None (1) |      0 |       1
    #       3 |      0       2 |       0 | None (2) |      0 |       2
    #       3 |      0       3 |       0 | None (3) |      0 | None (3)
    #       3 |      1       1 |       0 | None (1) |      1 |       1
    #       3 |      1       2 |       0 | None (2) |      1 | None (2)
    #       3 |      1       3 |       0 |       2  |      1 | None (2)
    #       3 |      2       1 |       0 | None (1) |      2 | None (1)
    #       3 |      2       2 |       0 |       1  |      2 | None (1)
    #       3 |      2       3 |       0 |       1  |      2 | None (1)

    # The following assert checks to make sure the call_seq obtained by
    # the get_formatted_call_seq has the correct number of entries and
    # is formatted correctly with arrows by calling seq_slice with the
    # get_formatted_call_seq seq_depth. In this case, the slice returned
    # by seq_slice should be exactly the same as the input
    if seq_depth is None:
        seq_depth = get_formatted_call_seq_depth

    if not call_seq == seq_slice(call_seq=call_seq, end=seq_depth):
        logger.debug(
            f"check 4: {call_seq=}, " f"{seq_slice(call_seq=call_seq, end=seq_depth)=}"
        )
    assert call_seq == seq_slice(call_seq=call_seq, end=seq_depth)

    if seq_latest is None:
        seq_latest = 0

    # if we have enough stack entries to test
    if seq_latest < len(exp_stack):
        if len(exp_stack) - seq_latest < seq_depth:  # if need to slice
            call_seq = seq_slice(call_seq=call_seq, end=len(exp_stack) - seq_latest)

        if len(exp_stack) <= seq_latest + seq_depth:
            if not call_seq == get_exp_seq(exp_stack=exp_stack, latest=seq_latest):
                logger.debug(
                    f"check 5: {call_seq=}, "
                    f"{get_exp_seq(exp_stack=exp_stack, latest=seq_latest)=}"
                )
            assert call_seq == get_exp_seq(exp_stack=exp_stack, latest=seq_latest)
        else:
            exp_seq = get_exp_seq(
                exp_stack=exp_stack, latest=seq_latest, depth=seq_depth
            )
            if not call_seq == exp_seq:
                logger.debug(f"check 6: {call_seq=}, {exp_seq=}")
            assert call_seq == get_exp_seq(
                exp_stack=exp_stack, latest=seq_latest, depth=seq_depth
            )


########################################################################
# update stack with new line number
########################################################################
def update_stack(exp_stack: Deque[CallerInfo], line_num: int, add: int) -> None:
    """Update the stack line number.

    Args:
        exp_stack: The expected stack of callers
        line_num: the new line number to replace the one in the stack
        add: number to add to line_num for python version 3.6 and 3.7
    """
    caller_info = exp_stack.pop()
    if sys.version_info[0] >= 4 or sys.version_info[1] >= 8:
        caller_info = caller_info._replace(line_num=line_num)
    else:
        caller_info = caller_info._replace(line_num=line_num + add)
    exp_stack.append(caller_info)


########################################################################
# TestDiagMsgCorrectSource
########################################################################
class TestDiagMsgCorrectSource:
    """Verify that we are testing with correctly built code."""

    ####################################################################
    # test_diag_msg_correct_source
    ####################################################################
    def test_diag_msg_correct_source(self) -> None:
        """Test diag_msg correct source."""
        if "TOX_ENV_NAME" in os.environ:
            verify_source(obj_to_check=diag_msg)


########################################################################
# Class to test get call sequence
########################################################################
class TestCallSeq:
    """Class the test get_formatted_call_sequence."""

    ####################################################################
    # Error test for depth too deep
    ####################################################################
    def test_get_call_seq_error1(self) -> None:
        """Test basic get formatted call sequence function."""
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestCallSeq",
            func_name="test_get_call_seq_error1",
            line_num=420,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=541, add=0)
        call_seq = get_formatted_call_sequence()

        verify_call_seq(exp_stack=exp_stack, call_seq=call_seq)

        call_seq = get_formatted_call_sequence(latest=1000, depth=1001)

        assert call_seq == ""

        save_getframe = sys._getframe
        sys._getframe = None  # type: ignore

        call_seq = get_formatted_call_sequence()

        sys._getframe = save_getframe

        assert call_seq == ""

    ####################################################################
    # Basic test for get_formatted_call_seq
    ####################################################################
    def test_get_call_seq_basic(self) -> None:
        """Test basic get formatted call sequence function."""
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestCallSeq",
            func_name="test_get_call_seq_basic",
            line_num=420,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=572, add=0)
        call_seq = get_formatted_call_sequence()

        verify_call_seq(exp_stack=exp_stack, call_seq=call_seq)

    ####################################################################
    # Test with latest and depth parms with stack of 1
    ####################################################################
    def test_get_call_seq_with_parms(
        self, latest_arg: Optional[int] = None, depth_arg: Optional[int] = None
    ) -> None:
        """Test get_formatted_call_seq with parms at depth 1.

        Args:
            latest_arg: pytest fixture that specifies how far back into
                          the stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to
                         get

        """
        print("sys.version_info[0]:", sys.version_info[0])
        print("sys.version_info[1]:", sys.version_info[1])
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestCallSeq",
            func_name="test_get_call_seq_with_parms",
            line_num=449,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=604, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=607, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=610, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=613, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=622, add=2)
        self.get_call_seq_depth_2(
            exp_stack=exp_stack, latest_arg=latest_arg, depth_arg=depth_arg
        )

    ####################################################################
    # Test with latest and depth parms with stack of 2
    ####################################################################
    def get_call_seq_depth_2(
        self,
        exp_stack: Deque[CallerInfo],
        latest_arg: Optional[int] = None,
        depth_arg: Optional[int] = None,
    ) -> None:
        """Test get_formatted_call_seq at depth 2.

        Args:
            exp_stack: The expected stack of callers
            latest_arg: pytest fixture that specifies how far back into
                          the stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to
                                get

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestCallSeq",
            func_name="get_call_seq_depth_2",
            line_num=494,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=655, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=658, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=661, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=664, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=673, add=2)
        self.get_call_seq_depth_3(
            exp_stack=exp_stack, latest_arg=latest_arg, depth_arg=depth_arg
        )

        exp_stack.pop()  # return with correct stack

    ####################################################################
    # Test with latest and depth parms with stack of 3
    ####################################################################
    def get_call_seq_depth_3(
        self,
        exp_stack: Deque[CallerInfo],
        latest_arg: Optional[int] = None,
        depth_arg: Optional[int] = None,
    ) -> None:
        """Test get_formatted_call_seq at depth 3.

        Args:
            exp_stack: The expected stack of callers
            latest_arg: pytest fixture that specifies how far back into
                          the stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to
                         get

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestCallSeq",
            func_name="get_call_seq_depth_3",
            line_num=541,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=708, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=711, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=714, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=717, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=726, add=2)
        self.get_call_seq_depth_4(
            exp_stack=exp_stack, latest_arg=latest_arg, depth_arg=depth_arg
        )

        exp_stack.pop()  # return with correct stack

    ####################################################################
    # Test with latest and depth parms with stack of 4
    ####################################################################
    def get_call_seq_depth_4(
        self,
        exp_stack: Deque[CallerInfo],
        latest_arg: Optional[int] = None,
        depth_arg: Optional[int] = None,
    ) -> None:
        """Test get_formatted_call_seq at depth 4.

        Args:
            exp_stack: The expected stack of callers
            latest_arg: pytest fixture that specifies how far back into
                          the stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to
                         get

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestCallSeq",
            func_name="get_call_seq_depth_4",
            line_num=588,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=761, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=764, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=767, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=770, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        exp_stack.pop()  # return with correct stack

    ####################################################################
    # Verify we can run off the end of the stack
    ####################################################################
    def test_get_call_seq_full_stack(self) -> None:
        """Test to ensure we can run the entire stack."""
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestCallSeq",
            func_name="test_get_call_seq_full_stack",
            line_num=620,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=797, add=0)
        num_items = 0
        new_count = 1
        while num_items + 1 == new_count:
            call_seq = get_formatted_call_sequence(latest=0, depth=new_count)
            call_seq_list = call_seq.split()
            # The call_seq_list will have x call items and x-1 arrows,
            # so the following code will calculate the number of items
            # by adding 1 more arrow and dividing the sum by 2
            num_items = (len(call_seq_list) + 1) // 2
            verify_call_seq(
                exp_stack=exp_stack,
                call_seq=call_seq,
                seq_latest=0,
                seq_depth=num_items,
            )
            new_count += 1

        assert new_count > 2  # make sure we tried more than 1


########################################################################
# TestDiagMsg class
########################################################################
class TestDiagMsg:
    """Class to test msg_diag."""

    DT1: Final = 0b00001000
    DEPTH1: Final = 0b00000100
    MSG1: Final = 0b00000010
    FILE1: Final = 0b00000001

    DT0_DEPTH0_MSG0_FILE0: Final = 0b00000000
    DT0_DEPTH0_MSG0_FILE1: Final = 0b00000001
    DT0_DEPTH0_MSG1_FILE0: Final = 0b00000010
    DT0_DEPTH0_MSG1_FILE1: Final = 0b00000011
    DT0_DEPTH1_MSG0_FILE0: Final = 0b00000100
    DT0_DEPTH1_MSG0_FILE1: Final = 0b00000101
    DT0_DEPTH1_MSG1_FILE0: Final = 0b00000110
    DT0_DEPTH1_MSG1_FILE1: Final = 0b00000111
    DT1_DEPTH0_MSG0_FILE0: Final = 0b00001000
    DT1_DEPTH0_MSG0_FILE1: Final = 0b00001001
    DT1_DEPTH0_MSG1_FILE0: Final = 0b00001010
    DT1_DEPTH0_MSG1_FILE1: Final = 0b00001011
    DT1_DEPTH1_MSG0_FILE0: Final = 0b00001100
    DT1_DEPTH1_MSG0_FILE1: Final = 0b00001101
    DT1_DEPTH1_MSG1_FILE0: Final = 0b00001110
    DT1_DEPTH1_MSG1_FILE1: Final = 0b00001111

    ####################################################################
    # Get the arg specifications for diag_msg
    ####################################################################
    @staticmethod
    def get_diag_msg_args(
        *,
        dt_format_arg: Optional[str] = None,
        depth_arg: Optional[int] = None,
        msg_arg: Optional[List[Union[str, int]]] = None,
        file_arg: Optional[str] = None,
    ) -> DiagMsgArgs:
        """Static method get_arg_flags.

        Args:
            dt_format_arg: dt_format arg to use for diag_msg
            depth_arg: depth arg to use for diag_msg
            msg_arg: message to specify on the diag_msg
            file_arg: file arg to use (stdout or stderr) on diag_msg

        Returns:
              the expected results based on the args
        """
        a_arg_bits = TestDiagMsg.DT0_DEPTH0_MSG0_FILE0

        a_dt_format_arg = diag_msg_datetime_fmt
        if dt_format_arg is not None:
            a_arg_bits = a_arg_bits | TestDiagMsg.DT1
            a_dt_format_arg = dt_format_arg

        a_depth_arg = diag_msg_caller_depth
        if depth_arg is not None:
            a_arg_bits = a_arg_bits | TestDiagMsg.DEPTH1
            a_depth_arg = depth_arg

        a_msg_arg: List[Union[str, int]] = [""]
        if msg_arg is not None:
            a_arg_bits = a_arg_bits | TestDiagMsg.MSG1
            a_msg_arg = msg_arg

        a_file_arg = "sys.stdout"
        if file_arg is not None:
            a_arg_bits = a_arg_bits | TestDiagMsg.FILE1
            a_file_arg = file_arg

        return DiagMsgArgs(
            arg_bits=a_arg_bits,
            dt_format_arg=a_dt_format_arg,
            depth_arg=a_depth_arg,
            msg_arg=a_msg_arg,
            file_arg=a_file_arg,
        )

    ####################################################################
    # Basic diag_msg test
    ####################################################################
    def test_diag_msg_basic(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test various combinations of msg_diag.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestDiagMsg",
            func_name="test_diag_msg_basic",
            line_num=727,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=914, add=0)
        before_time = datetime.now()
        diag_msg()
        after_time = datetime.now()

        diag_msg_args = self.get_diag_msg_args()
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

    ####################################################################
    # diag_msg with parms
    ####################################################################
    @etrace
    def test_diag_msg_with_parms(
        self,
        capsys: pytest.CaptureFixture[str],
        dt_format_arg: str,
        depth_arg: int,
        msg_arg: List[Union[str, int]],
        file_arg: str,
    ) -> None:
        """Test various combinations of msg_diag.

        Args:
            capsys: pytest fixture that captures output
            dt_format_arg: pytest fixture for datetime format
            depth_arg: pytest fixture for number of call seq entries
            msg_arg: pytest fixture for messages
            file_arg: pytest fixture for different print file types

        """
        # %m/%d/%Y %H:%M:%S-0-msg_arg0-sys_stdout
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestDiagMsg",
            func_name="test_diag_msg_with_parms",
            line_num=768,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=966, add=0)
        diag_msg_args = self.get_diag_msg_args(
            dt_format_arg=dt_format_arg,
            depth_arg=depth_arg,
            msg_arg=msg_arg,
            file_arg=file_arg,
        )
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=969, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=972, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=975, add=0)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=978, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=981, add=0)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=984, add=0)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=987, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=994, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=997, add=2)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1002, add=0)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1005, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1012, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1017, add=4)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1024, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1031, add=5)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )

        after_time = datetime.now()

        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        update_stack(exp_stack=exp_stack, line_num=1049, add=2)
        self.diag_msg_depth_2(
            exp_stack=exp_stack, capsys=capsys, diag_msg_args=diag_msg_args
        )

    ####################################################################
    # Depth 2 test
    ####################################################################
    def diag_msg_depth_2(
        self,
        exp_stack: Deque[CallerInfo],
        capsys: pytest.CaptureFixture[str],
        diag_msg_args: DiagMsgArgs,
    ) -> None:
        """Test msg_diag with two callers in the sequence.

        Args:
            exp_stack: The expected stack as modified by each test case
            capsys: pytest fixture that captures output
            diag_msg_args: Specifies the args to use on the diag_msg
                             invocation

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestDiagMsg",
            func_name="diag_msg_depth_2",
            line_num=867,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=1081, add=0)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1084, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1087, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1090, add=0)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1093, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1096, add=0)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1099, add=0)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1102, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1109, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1112, add=2)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1117, add=0)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1120, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1127, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1132, add=4)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1139, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1146, add=5)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )

        after_time = datetime.now()

        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        update_stack(exp_stack=exp_stack, line_num=1164, add=2)
        self.diag_msg_depth_3(
            exp_stack=exp_stack, capsys=capsys, diag_msg_args=diag_msg_args
        )

        exp_stack.pop()  # return with correct stack

    ####################################################################
    # Depth 3 test
    ####################################################################
    def diag_msg_depth_3(
        self,
        exp_stack: Deque[CallerInfo],
        capsys: pytest.CaptureFixture[str],
        diag_msg_args: DiagMsgArgs,
    ) -> None:
        """Test msg_diag with three callers in the sequence.

        Args:
            exp_stack: The expected stack as modified by each test case
            capsys: pytest fixture that captures output
            diag_msg_args: Specifies the args to use on the diag_msg
                             invocation

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestDiagMsg",
            func_name="diag_msg_depth_3",
            line_num=968,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=1198, add=0)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1201, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1204, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1207, add=0)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1210, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1213, add=0)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1216, add=0)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1219, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1226, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1229, add=2)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1234, add=0)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1237, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1244, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1249, add=4)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1256, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1263, add=5)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )

        after_time = datetime.now()

        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        exp_stack.pop()  # return with correct stack


########################################################################
# The functions and classes below handle various combinations of cases
# where one function calls another up to a level of 5 functions deep.
# The first caller can be at the module level (i.e., script level), or a
# module function, class method, static method, or class method. The
# second and subsequent callers can be any but the module level caller.
# The following grouping shows the possibilities:
# {mod, func, method, static_method, cls_method}
#       -> {func, method, static_method, cls_method}
#
########################################################################
# func 0
########################################################################
def test_func_get_caller_info_0(capsys: pytest.CaptureFixture[str]) -> None:
    """Module level function 0 to test get_caller_info.

    Args:
        capsys: Pytest fixture that captures output
    """
    exp_stack: Deque[CallerInfo] = deque()
    exp_caller_info = CallerInfo(
        mod_name="test_diag_msg.py",
        cls_name="",
        func_name="test_func_get_caller_info_0",
        line_num=1071,
    )
    exp_stack.append(exp_caller_info)
    update_stack(exp_stack=exp_stack, line_num=1314, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=1321, add=0)
    call_seq = get_formatted_call_sequence(depth=1)

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    update_stack(exp_stack=exp_stack, line_num=1328, add=0)
    before_time = datetime.now()
    diag_msg("message 0", 0, depth=1)
    after_time = datetime.now()

    diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1, msg_arg=["message 0", 0])
    verify_diag_msg(
        exp_stack=exp_stack,
        before_time=before_time,
        after_time=after_time,
        capsys=capsys,
        diag_msg_args=diag_msg_args,
    )

    # call module level function
    update_stack(exp_stack=exp_stack, line_num=1342, add=0)
    func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info1 = ClassGetCallerInfo1()
    update_stack(exp_stack=exp_stack, line_num=1347, add=0)
    cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=1351, add=0)
    cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=1355, add=0)
    ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=1359, add=0)
    cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=1363, add=0)
    cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=1367, add=0)
    ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info1s = ClassGetCallerInfo1S()
    update_stack(exp_stack=exp_stack, line_num=1372, add=0)
    cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=1376, add=0)
    cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=1380, add=0)
    ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=1384, add=0)
    cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=1388, add=0)
    cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=1392, add=0)
    ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=1396, add=0)
    cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=1400, add=0)
    cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=1404, add=0)
    ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

    ####################################################################
    # Inner class defined inside function test_func_get_caller_info_0
    ####################################################################
    class Inner:
        """Inner class for testing with inner class."""

        def __init__(self) -> None:
            """Initialize Inner class object."""
            self.var2 = 2

        def g1(self, exp_stack_g: Deque[CallerInfo], capsys_g: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_g: The expected call stack
                capsys_g: Pytest fixture that captures output

            """
            exp_caller_info_g = CallerInfo(
                mod_name="test_diag_msg.py",
                cls_name="Inner",
                func_name="g1",
                line_num=1197,
            )
            exp_stack_g.append(exp_caller_info_g)
            update_stack(exp_stack=exp_stack_g, line_num=1435, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1442, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1450, add=0)
                before_time_g = datetime.now()
                diag_msg("message 1", 1, depth=len(exp_stack_g))
                after_time_g = datetime.now()

                diag_msg_args_g = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_g), msg_arg=["message 1", 1]
                )
                verify_diag_msg(
                    exp_stack=exp_stack_g,
                    before_time=before_time_g,
                    after_time=after_time_g,
                    capsys=capsys_g,
                    diag_msg_args=diag_msg_args_g,
                )

            # call module level function
            update_stack(exp_stack=exp_stack_g, line_num=1466, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1471, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1477, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1483, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1489, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1495, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1501, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1508, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1514, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1520, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1526, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1532, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1538, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1544, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1550, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1556, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            exp_stack.pop()

        @staticmethod
        def g2_static(exp_stack_g: Deque[CallerInfo], capsys_g: Optional[Any]) -> None:
            """Inner static method to test diag msg.

            Args:
                exp_stack_g: The expected call stack
                capsys_g: Pytest fixture that captures output

            """
            exp_caller_info_g = CallerInfo(
                mod_name="test_diag_msg.py",
                cls_name="Inner",
                func_name="g2_static",
                line_num=1197,
            )
            exp_stack_g.append(exp_caller_info_g)
            update_stack(exp_stack=exp_stack_g, line_num=1582, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1589, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1597, add=0)
                before_time_g = datetime.now()
                diag_msg("message 1", 1, depth=len(exp_stack_g))
                after_time_g = datetime.now()

                diag_msg_args_g = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_g), msg_arg=["message 1", 1]
                )
                verify_diag_msg(
                    exp_stack=exp_stack_g,
                    before_time=before_time_g,
                    after_time=after_time_g,
                    capsys=capsys_g,
                    diag_msg_args=diag_msg_args_g,
                )

            # call module level function
            update_stack(exp_stack=exp_stack_g, line_num=1613, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1618, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1624, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1630, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1636, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1642, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1648, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1655, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1661, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1667, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1673, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1679, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1685, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1691, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1697, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1703, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            exp_stack.pop()

        @classmethod
        def g3_class(
            cls, exp_stack_g: Deque[CallerInfo], capsys_g: Optional[Any]
        ) -> None:
            """Inner class method to test diag msg.

            Args:
                exp_stack_g: The expected call stack
                capsys_g: Pytest fixture that captures output

            """
            exp_caller_info_g = CallerInfo(
                mod_name="test_diag_msg.py",
                cls_name="Inner",
                func_name="g3_class",
                line_num=1197,
            )
            exp_stack_g.append(exp_caller_info_g)
            update_stack(exp_stack=exp_stack_g, line_num=1731, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1738, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1746, add=0)
                before_time_g = datetime.now()
                diag_msg("message 1", 1, depth=len(exp_stack_g))
                after_time_g = datetime.now()

                diag_msg_args_g = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_g), msg_arg=["message 1", 1]
                )
                verify_diag_msg(
                    exp_stack=exp_stack_g,
                    before_time=before_time_g,
                    after_time=after_time_g,
                    capsys=capsys_g,
                    diag_msg_args=diag_msg_args_g,
                )

            # call module level function
            update_stack(exp_stack=exp_stack_g, line_num=1762, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1767, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1773, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1779, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1785, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1791, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1797, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1804, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1810, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1816, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1822, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1828, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1834, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1840, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1846, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1852, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            exp_stack.pop()

    class Inherit(Inner):
        """Inherit class for testing inner class."""

        def __init__(self) -> None:
            """Initialize Inherit object."""
            super().__init__()
            self.var3 = 3

        def h1(self, exp_stack_h: Deque[CallerInfo], capsys_h: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_h: The expected call stack
                capsys_h: Pytest fixture that captures output

            """
            exp_caller_info_h = CallerInfo(
                mod_name="test_diag_msg.py",
                cls_name="Inherit",
                func_name="h1",
                line_num=1197,
            )
            exp_stack_h.append(exp_caller_info_h)
            update_stack(exp_stack=exp_stack_h, line_num=1885, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=1892, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=1900, add=0)
                before_time_h = datetime.now()
                diag_msg("message 1", 1, depth=len(exp_stack_h))
                after_time_h = datetime.now()

                diag_msg_args_h = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_h), msg_arg=["message 1", 1]
                )
                verify_diag_msg(
                    exp_stack=exp_stack_h,
                    before_time=before_time_h,
                    after_time=after_time_h,
                    capsys=capsys_h,
                    diag_msg_args=diag_msg_args_h,
                )

            # call module level function
            update_stack(exp_stack=exp_stack_h, line_num=1916, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=1921, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=1927, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=1933, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=1939, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=1945, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=1951, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=1958, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1964, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1970, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1976, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1982, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1988, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1994, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2000, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2006, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

        @staticmethod
        def h2_static(exp_stack_h: Deque[CallerInfo], capsys_h: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_h: The expected call stack
                capsys_h: Pytest fixture that captures output

            """
            exp_caller_info_h = CallerInfo(
                mod_name="test_diag_msg.py",
                cls_name="Inherit",
                func_name="h2_static",
                line_num=1197,
            )
            exp_stack_h.append(exp_caller_info_h)
            update_stack(exp_stack=exp_stack_h, line_num=2032, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2039, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2047, add=0)
                before_time_h = datetime.now()
                diag_msg("message 1", 1, depth=len(exp_stack_h))
                after_time_h = datetime.now()

                diag_msg_args_h = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_h), msg_arg=["message 1", 1]
                )
                verify_diag_msg(
                    exp_stack=exp_stack_h,
                    before_time=before_time_h,
                    after_time=after_time_h,
                    capsys=capsys_h,
                    diag_msg_args=diag_msg_args_h,
                )

            # call module level function
            update_stack(exp_stack=exp_stack_h, line_num=2063, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=2068, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2074, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2080, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2086, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2092, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2098, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=2105, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2111, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2117, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2123, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2129, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2135, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2141, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2147, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2153, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

        @classmethod
        def h3_class(
            cls, exp_stack_h: Deque[CallerInfo], capsys_h: Optional[Any]
        ) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_h: The expected call stack
                capsys_h: Pytest fixture that captures output

            """
            exp_caller_info_h = CallerInfo(
                mod_name="test_diag_msg.py",
                cls_name="Inherit",
                func_name="h3_class",
                line_num=1197,
            )
            exp_stack_h.append(exp_caller_info_h)
            update_stack(exp_stack=exp_stack_h, line_num=2181, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2188, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2196, add=0)
                before_time_h = datetime.now()
                diag_msg("message 1", 1, depth=len(exp_stack_h))
                after_time_h = datetime.now()

                diag_msg_args_h = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_h), msg_arg=["message 1", 1]
                )
                verify_diag_msg(
                    exp_stack=exp_stack_h,
                    before_time=before_time_h,
                    after_time=after_time_h,
                    capsys=capsys_h,
                    diag_msg_args=diag_msg_args_h,
                )

            # call module level function
            update_stack(exp_stack=exp_stack_h, line_num=2212, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=2217, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2223, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2229, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2235, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2241, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2247, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=2254, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2260, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2266, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2272, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2278, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2284, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2290, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2296, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2302, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

    a_inner = Inner()
    # call Inner method
    update_stack(exp_stack=exp_stack, line_num=2311, add=0)
    a_inner.g1(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2314, add=0)
    a_inner.g2_static(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2317, add=0)
    a_inner.g3_class(exp_stack_g=exp_stack, capsys_g=capsys)

    a_inherit = Inherit()

    update_stack(exp_stack=exp_stack, line_num=2322, add=0)
    a_inherit.h1(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2325, add=0)
    a_inherit.h2_static(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2328, add=0)
    a_inherit.h3_class(exp_stack_h=exp_stack, capsys_h=capsys)

    exp_stack.pop()


########################################################################
# func 1
########################################################################
def func_get_caller_info_1(exp_stack: Deque[CallerInfo], capsys: Optional[Any]) -> None:
    """Module level function 1 to test get_caller_info.

    Args:
        exp_stack: The expected call stack
        capsys: Pytest fixture that captures output

    """
    exp_caller_info = CallerInfo(
        mod_name="test_diag_msg.py",
        cls_name="",
        func_name="func_get_caller_info_1",
        line_num=1197,
    )
    exp_stack.append(exp_caller_info)
    update_stack(exp_stack=exp_stack, line_num=2355, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=2362, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=2370, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=len(exp_stack), msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

    # call module level function
    update_stack(exp_stack=exp_stack, line_num=2386, add=0)
    func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info2 = ClassGetCallerInfo2()
    update_stack(exp_stack=exp_stack, line_num=2391, add=0)
    cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=2395, add=0)
    cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=2399, add=0)
    ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=2403, add=0)
    cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=2407, add=0)
    cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=2411, add=0)
    ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info2s = ClassGetCallerInfo2S()
    update_stack(exp_stack=exp_stack, line_num=2416, add=0)
    cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=2420, add=0)
    cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=2424, add=0)
    ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=2428, add=0)
    cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=2432, add=0)
    cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=2436, add=0)
    ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=2440, add=0)
    cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=2444, add=0)
    cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=2448, add=0)
    ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

    ####################################################################
    # Inner class defined inside function test_func_get_caller_info_0
    ####################################################################
    class Inner:
        """Inner class for testing with inner class."""

        def __init__(self) -> None:
            """Initialize Inner class object."""
            self.var2 = 2

        def g1(self, exp_stack_g: Deque[CallerInfo], capsys_g: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_g: The expected call stack
                capsys_g: Pytest fixture that captures output

            """
            exp_caller_info_g = CallerInfo(
                mod_name="test_diag_msg.py",
                cls_name="Inner",
                func_name="g1",
                line_num=1197,
            )
            exp_stack_g.append(exp_caller_info_g)
            update_stack(exp_stack=exp_stack_g, line_num=2479, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2486, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2494, add=0)
                before_time_g = datetime.now()
                diag_msg("message 1", 1, depth=len(exp_stack_g))
                after_time_g = datetime.now()

                diag_msg_args_g = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_g), msg_arg=["message 1", 1]
                )
                verify_diag_msg(
                    exp_stack=exp_stack_g,
                    before_time=before_time_g,
                    after_time=after_time_g,
                    capsys=capsys_g,
                    diag_msg_args=diag_msg_args_g,
                )

            # call module level function
            update_stack(exp_stack=exp_stack_g, line_num=2510, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2515, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2521, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2527, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2533, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2539, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2545, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2552, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2558, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2564, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2570, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2576, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2582, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2588, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2594, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2600, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            exp_stack.pop()

        @staticmethod
        def g2_static(exp_stack_g: Deque[CallerInfo], capsys_g: Optional[Any]) -> None:
            """Inner static method to test diag msg.

            Args:
                exp_stack_g: The expected call stack
                capsys_g: Pytest fixture that captures output

            """
            exp_caller_info_g = CallerInfo(
                mod_name="test_diag_msg.py",
                cls_name="Inner",
                func_name="g2_static",
                line_num=2297,
            )
            exp_stack_g.append(exp_caller_info_g)
            update_stack(exp_stack=exp_stack_g, line_num=2626, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2633, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2641, add=0)
                before_time_g = datetime.now()
                diag_msg("message 1", 1, depth=len(exp_stack_g))
                after_time_g = datetime.now()

                diag_msg_args_g = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_g), msg_arg=["message 1", 1]
                )
                verify_diag_msg(
                    exp_stack=exp_stack_g,
                    before_time=before_time_g,
                    after_time=after_time_g,
                    capsys=capsys_g,
                    diag_msg_args=diag_msg_args_g,
                )

            # call module level function
            update_stack(exp_stack=exp_stack_g, line_num=2657, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2662, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2668, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2674, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2680, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2686, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2692, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2699, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2705, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2711, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2717, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2723, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2729, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2735, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2741, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2747, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            exp_stack.pop()

        @classmethod
        def g3_class(
            cls, exp_stack_g: Deque[CallerInfo], capsys_g: Optional[Any]
        ) -> None:
            """Inner class method to test diag msg.

            Args:
                exp_stack_g: The expected call stack
                capsys_g: Pytest fixture that captures output

            """
            exp_caller_info_g = CallerInfo(
                mod_name="test_diag_msg.py",
                cls_name="Inner",
                func_name="g3_class",
                line_num=2197,
            )
            exp_stack_g.append(exp_caller_info_g)
            update_stack(exp_stack=exp_stack_g, line_num=2775, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2782, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2790, add=0)
                before_time_g = datetime.now()
                diag_msg("message 1", 1, depth=len(exp_stack_g))
                after_time_g = datetime.now()

                diag_msg_args_g = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_g), msg_arg=["message 1", 1]
                )
                verify_diag_msg(
                    exp_stack=exp_stack_g,
                    before_time=before_time_g,
                    after_time=after_time_g,
                    capsys=capsys_g,
                    diag_msg_args=diag_msg_args_g,
                )

            # call module level function
            update_stack(exp_stack=exp_stack_g, line_num=2806, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2811, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2817, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2823, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2829, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2835, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2841, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2848, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2854, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2860, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2866, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2872, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2878, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2884, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2890, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2896, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            exp_stack.pop()

    class Inherit(Inner):
        """Inherit class for testing inner class."""

        def __init__(self) -> None:
            """Initialize Inherit object."""
            super().__init__()
            self.var3 = 3

        def h1(self, exp_stack_h: Deque[CallerInfo], capsys_h: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_h: The expected call stack
                capsys_h: Pytest fixture that captures output

            """
            exp_caller_info_h = CallerInfo(
                mod_name="test_diag_msg.py",
                cls_name="Inherit",
                func_name="h1",
                line_num=1197,
            )
            exp_stack_h.append(exp_caller_info_h)
            update_stack(exp_stack=exp_stack_h, line_num=2929, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2936, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2944, add=0)
                before_time_h = datetime.now()
                diag_msg("message 1", 1, depth=len(exp_stack_h))
                after_time_h = datetime.now()

                diag_msg_args_h = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_h), msg_arg=["message 1", 1]
                )
                verify_diag_msg(
                    exp_stack=exp_stack_h,
                    before_time=before_time_h,
                    after_time=after_time_h,
                    capsys=capsys_h,
                    diag_msg_args=diag_msg_args_h,
                )

            # call module level function
            update_stack(exp_stack=exp_stack_h, line_num=2960, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2965, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2971, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2977, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2983, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2989, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2995, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=3002, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3008, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3014, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3020, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3026, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3032, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3038, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3044, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3050, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

        @staticmethod
        def h2_static(exp_stack_h: Deque[CallerInfo], capsys_h: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_h: The expected call stack
                capsys_h: Pytest fixture that captures output

            """
            exp_caller_info_h = CallerInfo(
                mod_name="test_diag_msg.py",
                cls_name="Inherit",
                func_name="h2_static",
                line_num=1197,
            )
            exp_stack_h.append(exp_caller_info_h)
            update_stack(exp_stack=exp_stack_h, line_num=3076, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=3083, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=3091, add=0)
                before_time_h = datetime.now()
                diag_msg("message 1", 1, depth=len(exp_stack_h))
                after_time_h = datetime.now()

                diag_msg_args_h = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_h), msg_arg=["message 1", 1]
                )
                verify_diag_msg(
                    exp_stack=exp_stack_h,
                    before_time=before_time_h,
                    after_time=after_time_h,
                    capsys=capsys_h,
                    diag_msg_args=diag_msg_args_h,
                )

            # call module level function
            update_stack(exp_stack=exp_stack_h, line_num=3107, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=3112, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=3118, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=3124, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=3130, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=3136, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=3142, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=3149, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3155, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3161, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3167, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3173, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3179, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3185, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3191, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3197, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

        @classmethod
        def h3_class(
            cls, exp_stack_h: Deque[CallerInfo], capsys_h: Optional[Any]
        ) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_h: The expected call stack
                capsys_h: Pytest fixture that captures output

            """
            exp_caller_info_h = CallerInfo(
                mod_name="test_diag_msg.py",
                cls_name="Inherit",
                func_name="h3_class",
                line_num=1197,
            )
            exp_stack_h.append(exp_caller_info_h)
            update_stack(exp_stack=exp_stack_h, line_num=3225, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=3232, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=3240, add=0)
                before_time_h = datetime.now()
                diag_msg("message 1", 1, depth=len(exp_stack_h))
                after_time_h = datetime.now()

                diag_msg_args_h = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_h), msg_arg=["message 1", 1]
                )
                verify_diag_msg(
                    exp_stack=exp_stack_h,
                    before_time=before_time_h,
                    after_time=after_time_h,
                    capsys=capsys_h,
                    diag_msg_args=diag_msg_args_h,
                )

            # call module level function
            update_stack(exp_stack=exp_stack_h, line_num=3256, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=3261, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=3267, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=3273, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=3279, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=3285, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=3291, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=3298, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3304, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3310, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3316, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3322, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3328, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3334, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3340, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3346, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

    a_inner = Inner()
    # call Inner method
    update_stack(exp_stack=exp_stack, line_num=3355, add=0)
    a_inner.g1(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=3358, add=0)
    a_inner.g2_static(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=3361, add=0)
    a_inner.g3_class(exp_stack_g=exp_stack, capsys_g=capsys)

    a_inherit = Inherit()

    update_stack(exp_stack=exp_stack, line_num=3366, add=0)
    a_inherit.h1(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=3369, add=0)
    a_inherit.h2_static(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=3372, add=0)
    a_inherit.h3_class(exp_stack_h=exp_stack, capsys_h=capsys)

    exp_stack.pop()


########################################################################
# func 2
########################################################################
def func_get_caller_info_2(exp_stack: Deque[CallerInfo], capsys: Optional[Any]) -> None:
    """Module level function 1 to test get_caller_info.

    Args:
        exp_stack: The expected call stack
        capsys: Pytest fixture that captures output

    """
    exp_caller_info = CallerInfo(
        mod_name="test_diag_msg.py",
        cls_name="",
        func_name="func_get_caller_info_2",
        line_num=1324,
    )
    exp_stack.append(exp_caller_info)
    update_stack(exp_stack=exp_stack, line_num=3399, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=3406, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3414, add=0)
        before_time = datetime.now()
        diag_msg("message 2", 2, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=len(exp_stack), msg_arg=["message 2", 2]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

    # call module level function
    update_stack(exp_stack=exp_stack, line_num=3430, add=0)
    func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info3 = ClassGetCallerInfo3()
    update_stack(exp_stack=exp_stack, line_num=3435, add=0)
    cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=3439, add=0)
    cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=3443, add=0)
    ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=3447, add=0)
    cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=3451, add=0)
    cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=3455, add=0)
    ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info3s = ClassGetCallerInfo3S()
    update_stack(exp_stack=exp_stack, line_num=3460, add=0)
    cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=3464, add=0)
    cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=3468, add=0)
    ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=3472, add=0)
    cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=3476, add=0)
    cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=3480, add=0)
    ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=3484, add=0)
    cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=3488, add=0)
    cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=3492, add=0)
    ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

    exp_stack.pop()


########################################################################
# func 3
########################################################################
def func_get_caller_info_3(exp_stack: Deque[CallerInfo], capsys: Optional[Any]) -> None:
    """Module level function 1 to test get_caller_info.

    Args:
        exp_stack: The expected call stack
        capsys: Pytest fixture that captures output

    """
    exp_caller_info = CallerInfo(
        mod_name="test_diag_msg.py",
        cls_name="",
        func_name="func_get_caller_info_3",
        line_num=1451,
    )
    exp_stack.append(exp_caller_info)
    update_stack(exp_stack=exp_stack, line_num=3519, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=3526, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3534, add=0)
        before_time = datetime.now()
        diag_msg("message 2", 2, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=len(exp_stack), msg_arg=["message 2", 2]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

    exp_stack.pop()


########################################################################
# Classes
########################################################################
########################################################################
# Class 0
########################################################################
class TestClassGetCallerInfo0:
    """Class to get caller info 0."""

    ####################################################################
    # Class 0 Method 1
    ####################################################################
    def test_get_caller_info_m0(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info method 1.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0",
            func_name="test_get_caller_info_m0",
            line_num=1509,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=3582, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3589, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3596, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=3612, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3617, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3621, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3625, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3629, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3633, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3637, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3642, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3646, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3650, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3654, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3658, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3662, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3666, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3670, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3674, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 2
    ####################################################################
    def test_get_caller_info_helper(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Get capsys for static methods.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0",
            func_name="test_get_caller_info_helper",
            line_num=1635,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=3697, add=0)
        self.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3699, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)

        update_stack(exp_stack=exp_stack, line_num=3702, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3704, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)

    @staticmethod
    def get_caller_info_s0(
        exp_stack: Deque[CallerInfo], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Get caller info static method 0.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0",
            func_name="get_caller_info_s0",
            line_num=1664,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=3728, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3735, add=0)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3742, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=2)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=2, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=3758, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3763, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3767, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3771, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3775, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3779, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3783, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3788, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3792, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3796, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3800, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3804, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3808, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3812, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3816, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3820, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 3
    ####################################################################
    @classmethod
    def test_get_caller_info_c0(cls, capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info class method 0.

        Args:
            capsys: Pytest fixture that captures output
        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0",
            func_name="test_get_caller_info_c0",
            line_num=1792,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=3846, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3853, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3860, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=3876, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3881, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3885, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3889, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3893, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3897, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3901, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3906, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3910, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3914, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3918, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3922, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3926, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3930, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3934, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3938, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 4
    ####################################################################
    def test_get_caller_info_m0bo(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0",
            func_name="test_get_caller_info_m0bo",
            line_num=1920,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=3964, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3971, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3978, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=3994, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3999, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4003, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4007, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4011, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4015, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4019, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4024, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4028, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4032, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4036, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4040, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4044, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4048, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4052, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4056, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 5
    ####################################################################
    @staticmethod
    def test_get_caller_info_s0bo(capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded static method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0",
            func_name="test_get_caller_info_s0bo",
            line_num=2048,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4083, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4090, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4097, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4113, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4118, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4122, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4126, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4130, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4134, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4138, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4143, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4147, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4151, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4155, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4159, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4163, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4167, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4171, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4175, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 6
    ####################################################################
    @classmethod
    def test_get_caller_info_c0bo(cls, capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0",
            func_name="test_get_caller_info_c0bo",
            line_num=2177,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4202, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4209, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4216, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4232, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4237, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4241, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4245, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4249, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4253, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4257, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4262, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4266, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4270, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4274, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4278, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4282, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4286, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4290, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4294, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 7
    ####################################################################
    def test_get_caller_info_m0bt(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0",
            func_name="test_get_caller_info_m0bt",
            line_num=2305,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4320, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4327, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4334, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=len(exp_stack), msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4350, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4355, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4359, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4363, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4367, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4371, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4375, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4380, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4384, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4388, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4392, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4396, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4400, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4404, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4408, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4412, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s0bt(
        exp_stack: Deque[CallerInfo], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Get caller info overloaded static method 0.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0",
            func_name="get_caller_info_s0bt",
            line_num=2434,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4441, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4448, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4455, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=len(exp_stack), msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4471, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4476, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4480, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4484, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4488, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4492, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4496, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4501, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4505, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4509, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4513, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4517, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4521, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4525, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4529, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4533, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 9
    ####################################################################
    @classmethod
    def test_get_caller_info_c0bt(cls, capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0",
            func_name="test_get_caller_info_c0bt",
            line_num=2567,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4560, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4567, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4574, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=len(exp_stack), msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4590, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4595, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4599, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4603, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4607, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4611, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4615, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4620, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4624, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4628, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4632, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4636, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4640, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4644, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4648, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4652, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 10
    ####################################################################
    @classmethod
    def get_caller_info_c0bt(
        cls, exp_stack: Optional[Deque[CallerInfo]], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Get caller info overloaded class method 0.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        if not exp_stack:
            exp_stack = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0",
            func_name="get_caller_info_c0bt",
            line_num=2567,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4683, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4690, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4697, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=len(exp_stack), msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4713, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4718, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4722, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4726, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4730, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4734, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4738, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4743, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4747, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4751, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4755, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4759, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4763, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4767, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4771, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4775, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()


########################################################################
# Class 0S
########################################################################
class TestClassGetCallerInfo0S(TestClassGetCallerInfo0):
    """Subclass to get caller info0."""

    ####################################################################
    # Class 0S Method 1
    ####################################################################
    def test_get_caller_info_m0s(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info method 0.

        Args:
            capsys: Pytest fixture that captures output
        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0S",
            func_name="test_get_caller_info_m0s",
            line_num=2701,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4807, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4814, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4821, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4837, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4842, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4846, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4850, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4854, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4858, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4862, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4867, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4871, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4875, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4879, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4883, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4887, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4891, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4895, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4899, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 2
    ####################################################################
    @staticmethod
    def test_get_caller_info_s0s(capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info static method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0S",
            func_name="test_get_caller_info_s0s",
            line_num=2829,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4926, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4933, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4940, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4956, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4961, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4965, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4969, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4973, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4977, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4981, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4986, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4990, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4994, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4998, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5002, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5006, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5010, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5014, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5018, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 3
    ####################################################################
    @classmethod
    def test_get_caller_info_c0s(cls, capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0S",
            func_name="test_get_caller_info_c0s",
            line_num=2958,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5045, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5052, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5059, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5075, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5080, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5084, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5088, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5092, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5096, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5100, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5105, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5109, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5113, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5117, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5121, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5125, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5129, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5133, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5137, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 4
    ####################################################################
    def test_get_caller_info_m0bo(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0S",
            func_name="test_get_caller_info_m0bo",
            line_num=3086,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5163, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5170, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5177, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5193, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5198, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5202, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5206, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5210, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5214, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5218, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5223, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5227, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5231, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5235, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5239, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5243, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5247, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5251, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5255, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 5
    ####################################################################
    @staticmethod
    def test_get_caller_info_s0bo(capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded static method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0S",
            func_name="test_get_caller_info_s0bo",
            line_num=3214,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5282, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5289, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5296, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5312, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5317, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5321, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5325, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5329, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5333, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5337, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5342, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5346, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5350, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5354, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5358, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5362, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5366, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5370, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5374, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 6
    ####################################################################
    @classmethod
    def test_get_caller_info_c0bo(cls, capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0S",
            func_name="test_get_caller_info_c0bo",
            line_num=3343,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5401, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5408, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5415, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5431, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5436, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5440, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5444, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5448, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5452, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5456, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5461, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5465, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5469, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5473, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5477, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5481, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5485, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5489, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5493, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 7
    ####################################################################
    def test_get_caller_info_m0sb(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0S",
            func_name="test_get_caller_info_m0sb",
            line_num=3471,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5519, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5526, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5533, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call base class normal method target
        update_stack(exp_stack=exp_stack, line_num=5549, add=0)
        self.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        update_stack(exp_stack=exp_stack, line_num=5552, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5555, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5559, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5561, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5563, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5565, add=2)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5571, add=0)
        super().get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5573, add=0)
        TestClassGetCallerInfo0.get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5575, add=2)
        TestClassGetCallerInfo0S.get_caller_info_c0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5581, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5586, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5590, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5594, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5598, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5602, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5606, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5611, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5615, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5619, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5623, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5627, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5631, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5635, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5639, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5643, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 8
    ####################################################################
    @staticmethod
    def test_get_caller_info_s0sb(capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded static method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0S",
            func_name="test_get_caller_info_s0sb",
            line_num=3631,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5670, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5677, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5684, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call base class normal method target
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        update_stack(exp_stack=exp_stack, line_num=5701, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5704, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5708, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5710, add=2)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5716, add=0)
        TestClassGetCallerInfo0.get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5718, add=2)
        TestClassGetCallerInfo0S.get_caller_info_c0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5724, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5729, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5733, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5737, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5741, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5745, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5749, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5754, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5758, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5762, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5766, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5770, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5774, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5778, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5782, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5786, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 9
    ####################################################################
    @classmethod
    def test_get_caller_info_c0sb(cls, capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestClassGetCallerInfo0S",
            func_name="test_get_caller_info_c0sb",
            line_num=3784,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5813, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5820, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5827, add=0)
        before_time = datetime.now()
        diag_msg("message 1", 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(
            depth_arg=1, msg_arg=["message 1", 1]
        )
        verify_diag_msg(
            exp_stack=exp_stack,
            before_time=before_time,
            after_time=after_time,
            capsys=capsys,
            diag_msg_args=diag_msg_args,
        )

        # call base class normal method target
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        update_stack(exp_stack=exp_stack, line_num=5844, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5847, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5851, add=0)
        cls.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5853, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5855, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5857, add=2)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )
        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5862, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5867, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5871, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5875, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5879, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5883, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5887, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5892, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5896, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5900, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5904, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5908, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5912, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5916, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5920, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5924, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()


########################################################################
# Class 1
########################################################################
class ClassGetCallerInfo1:
    """Class to get caller info1."""

    def __init__(self) -> None:
        """The initialization."""
        self.var1 = 1

    ####################################################################
    # Class 1 Method 1
    ####################################################################
    def get_caller_info_m1(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        self.var1 += 1
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1",
            func_name="get_caller_info_m1",
            line_num=3945,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5964, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5971, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=5978, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5995, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6000, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6004, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6008, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6012, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6016, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6020, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6025, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6029, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6033, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6037, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6041, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6045, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6049, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6053, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6057, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 2
    ####################################################################
    @staticmethod
    def get_caller_info_s1(exp_stack: Deque[CallerInfo], capsys: Optional[Any]) -> None:
        """Get caller info static method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1",
            func_name="get_caller_info_s1",
            line_num=4076,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6084, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6091, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6098, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6115, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6120, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6124, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6128, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6132, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6136, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6140, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6145, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6149, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6153, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6157, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6161, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6165, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6169, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6173, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6177, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 3
    ####################################################################
    @classmethod
    def get_caller_info_c1(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info class method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output
        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1",
            func_name="get_caller_info_c1",
            line_num=4207,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6205, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6212, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6219, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6236, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6241, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6245, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6249, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6253, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6257, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6261, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6266, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6270, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6274, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6278, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6282, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6286, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6290, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6294, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6298, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 4
    ####################################################################
    def get_caller_info_m1bo(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1",
            func_name="get_caller_info_m1bo",
            line_num=4338,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6326, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6333, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6340, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6357, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6362, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6366, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6370, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6374, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6378, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6382, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6387, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6391, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6395, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6399, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6403, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6407, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6411, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6415, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6419, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 5
    ####################################################################
    @staticmethod
    def get_caller_info_s1bo(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded static method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1",
            func_name="get_caller_info_s1bo",
            line_num=4469,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6448, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6455, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6462, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6479, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6484, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6488, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6492, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6496, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6500, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6504, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6509, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6513, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6517, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6521, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6525, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6529, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6533, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6537, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6541, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 6
    ####################################################################
    @classmethod
    def get_caller_info_c1bo(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded class method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1",
            func_name="get_caller_info_c1bo",
            line_num=4601,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6570, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6577, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6584, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6601, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6606, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6610, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6614, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6618, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6622, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6626, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6631, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6635, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6639, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6643, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6647, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6651, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6655, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6659, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6663, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 7
    ####################################################################
    def get_caller_info_m1bt(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        self.var1 += 1
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1",
            func_name="get_caller_info_m1bt",
            line_num=4733,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6692, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6699, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6706, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6723, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6728, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6732, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6736, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6740, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6744, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6748, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6753, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6757, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6761, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6765, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6769, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6773, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6777, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6781, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6785, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s1bt(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded static method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1",
            func_name="get_caller_info_s1bt",
            line_num=4864,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6814, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6821, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6828, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6845, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6850, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6854, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6858, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6862, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6866, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6870, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6875, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6879, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6883, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6887, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6891, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6895, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6899, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6903, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6907, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 9
    ####################################################################
    @classmethod
    def get_caller_info_c1bt(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded class method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1",
            func_name="get_caller_info_c1bt",
            line_num=4996,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6936, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6943, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6950, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6967, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6972, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6976, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6980, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6984, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6988, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6992, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6997, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7001, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7005, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7009, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7013, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7017, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7021, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7025, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7029, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()


########################################################################
# Class 1S
########################################################################
class ClassGetCallerInfo1S(ClassGetCallerInfo1):
    """Subclass to get caller info1."""

    def __init__(self) -> None:
        """The initialization for subclass 1."""
        super().__init__()
        self.var2 = 2

    ####################################################################
    # Class 1S Method 1
    ####################################################################
    def get_caller_info_m1s(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output
        """
        self.var1 += 1
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1S",
            func_name="get_caller_info_m1s",
            line_num=5139,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7069, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7076, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7083, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7100, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7105, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7109, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7113, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7117, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7121, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7125, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7130, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7134, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7138, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7142, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7146, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7150, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7154, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7158, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7162, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 2
    ####################################################################
    @staticmethod
    def get_caller_info_s1s(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info static method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1S",
            func_name="get_caller_info_s1s",
            line_num=5270,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7191, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7198, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7205, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7222, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7227, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7231, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7235, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7239, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7243, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7247, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7252, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7256, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7260, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7264, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7268, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7272, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7276, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7280, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7284, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 3
    ####################################################################
    @classmethod
    def get_caller_info_c1s(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info class method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1S",
            func_name="get_caller_info_c1s",
            line_num=5402,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7313, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7320, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7327, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7344, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7349, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7353, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7357, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7361, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7365, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7369, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7374, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7378, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7382, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7386, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7390, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7394, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7398, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7402, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7406, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 4
    ####################################################################
    def get_caller_info_m1bo(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1S",
            func_name="get_caller_info_m1bo",
            line_num=5533,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7434, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7441, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7448, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7465, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7470, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7474, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7478, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7482, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7486, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7490, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7495, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7499, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7503, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7507, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7511, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7515, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7519, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7523, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7527, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 5
    ####################################################################
    @staticmethod
    def get_caller_info_s1bo(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded static method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1S",
            func_name="get_caller_info_s1bo",
            line_num=5664,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7556, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7563, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7570, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7587, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7592, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7596, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7600, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7604, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7608, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7612, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7617, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7621, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7625, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7629, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7633, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7637, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7641, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7645, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7649, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 6
    ####################################################################
    @classmethod
    def get_caller_info_c1bo(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded class method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1S",
            func_name="get_caller_info_c1bo",
            line_num=5796,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7678, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7685, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7692, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7709, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7714, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7718, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7722, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7726, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7730, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7734, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7739, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7743, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7747, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7751, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7755, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7759, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7763, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7767, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7771, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 7
    ####################################################################
    def get_caller_info_m1sb(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1S",
            func_name="get_caller_info_m1sb",
            line_num=5927,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7799, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7806, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7813, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call base class normal method target
        update_stack(exp_stack=exp_stack, line_num=7830, add=0)
        self.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=7833, add=0)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7836, add=0)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7840, add=0)
        self.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7842, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7844, add=0)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7846, add=0)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7850, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7852, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7854, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7858, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7863, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7867, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7871, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7875, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7879, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7883, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7888, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7892, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7896, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7900, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7904, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7908, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7912, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7916, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7920, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s1sb(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded static method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1S",
            func_name="get_caller_info_s1sb",
            line_num=6092,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7949, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7956, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7963, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call base class normal method target
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=7981, add=0)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7984, add=0)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7988, add=0)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7990, add=0)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7994, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7996, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8000, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=8005, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8009, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8013, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8017, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8021, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8025, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=8030, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8034, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8038, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8042, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8046, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8050, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8054, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8058, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8062, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 9
    ####################################################################
    @classmethod
    def get_caller_info_c1sb(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded class method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo1S",
            func_name="get_caller_info_c1sb",
            line_num=6250,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8091, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8098, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8105, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call base class normal method target
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=8123, add=0)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=8126, add=0)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=8130, add=0)
        cls.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8132, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8134, add=0)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8136, add=0)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=8140, add=0)
        cls.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8142, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8144, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8146, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8150, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=8155, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8159, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8163, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8167, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8171, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8175, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=8180, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8184, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8188, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8192, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8196, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8200, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8204, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8208, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8212, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()


########################################################################
# Class 2
########################################################################
class ClassGetCallerInfo2:
    """Class to get caller info2."""

    def __init__(self) -> None:
        """The initialization."""
        self.var1 = 1

    ####################################################################
    # Class 2 Method 1
    ####################################################################
    def get_caller_info_m2(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        self.var1 += 1
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2",
            func_name="get_caller_info_m2",
            line_num=6428,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8252, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8259, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8266, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8283, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8288, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8292, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8296, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8300, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8304, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8308, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8313, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8317, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8321, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8325, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8329, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8333, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8337, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8341, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8345, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 2
    ####################################################################
    @staticmethod
    def get_caller_info_s2(exp_stack: Deque[CallerInfo], capsys: Optional[Any]) -> None:
        """Get caller info static method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2",
            func_name="get_caller_info_s2",
            line_num=6559,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8372, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8379, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8386, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8403, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8408, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8412, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8416, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8420, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8424, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8428, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8433, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8437, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8441, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8445, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8449, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8453, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8457, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8461, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8465, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 3
    ####################################################################
    @classmethod
    def get_caller_info_c2(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info class method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output
        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2",
            func_name="get_caller_info_c2",
            line_num=6690,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8493, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8500, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8507, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8524, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8529, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8533, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8537, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8541, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8545, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8549, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8554, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8558, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8562, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8566, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8570, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8574, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8578, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8582, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8586, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 4
    ####################################################################
    def get_caller_info_m2bo(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2",
            func_name="get_caller_info_m2bo",
            line_num=6821,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8614, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8621, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8628, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8645, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8650, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8654, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8658, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8662, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8666, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8670, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8675, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8679, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8683, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8687, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8691, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8695, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8699, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8703, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8707, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 5
    ####################################################################
    @staticmethod
    def get_caller_info_s2bo(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded static method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2",
            func_name="get_caller_info_s2bo",
            line_num=6952,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8736, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8743, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8750, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8767, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8772, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8776, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8780, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8784, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8788, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8792, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8797, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8801, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8805, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8809, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8813, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8817, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8821, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8825, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8829, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 6
    ####################################################################
    @classmethod
    def get_caller_info_c2bo(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded class method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2",
            func_name="get_caller_info_c2bo",
            line_num=7084,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8858, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8865, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8872, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8889, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8894, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8898, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8902, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8906, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8910, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8914, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8919, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8923, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8927, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8931, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8935, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8939, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8943, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8947, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8951, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 7
    ####################################################################
    def get_caller_info_m2bt(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        self.var1 += 1
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2",
            func_name="get_caller_info_m2bt",
            line_num=7216,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8980, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8987, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8994, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9011, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9016, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9020, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9024, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9028, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9032, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9036, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9041, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9045, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9049, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9053, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9057, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9061, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9065, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9069, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9073, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s2bt(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded static method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2",
            func_name="get_caller_info_s2bt",
            line_num=7347,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9102, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9109, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9116, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9133, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9138, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9142, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9146, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9150, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9154, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9158, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9163, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9167, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9171, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9175, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9179, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9183, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9187, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9191, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9195, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 9
    ####################################################################
    @classmethod
    def get_caller_info_c2bt(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded class method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2",
            func_name="get_caller_info_c2bt",
            line_num=7479,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9224, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9231, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9238, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9255, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9260, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9264, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9268, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9272, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9276, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9280, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9285, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9289, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9293, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9297, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9301, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9305, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9309, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9313, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9317, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()


########################################################################
# Class 2S
########################################################################
class ClassGetCallerInfo2S(ClassGetCallerInfo2):
    """Subclass to get caller info2."""

    def __init__(self) -> None:
        """The initialization for subclass 2."""
        super().__init__()
        self.var2 = 2

    ####################################################################
    # Class 2S Method 1
    ####################################################################
    def get_caller_info_m2s(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output
        """
        self.var1 += 1
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2S",
            func_name="get_caller_info_m2s",
            line_num=7622,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9357, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9364, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9371, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9388, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9393, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9397, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9401, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9405, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9409, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9413, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9418, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9422, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9426, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9430, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9434, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9438, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9442, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9446, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9450, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 2
    ####################################################################
    @staticmethod
    def get_caller_info_s2s(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info static method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2S",
            func_name="get_caller_info_s2s",
            line_num=7753,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9479, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9486, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9493, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9510, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9515, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9519, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9523, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9527, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9531, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9535, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9540, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9544, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9548, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9552, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9556, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9560, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9564, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9568, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9572, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 3
    ####################################################################
    @classmethod
    def get_caller_info_c2s(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info class method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2S",
            func_name="get_caller_info_c2s",
            line_num=7885,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9601, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9608, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9615, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9632, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9637, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9641, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9645, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9649, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9653, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9657, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9662, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9666, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9670, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9674, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9678, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9682, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9686, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9690, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9694, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 4
    ####################################################################
    def get_caller_info_m2bo(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2S",
            func_name="get_caller_info_m2bo",
            line_num=8016,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9722, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9729, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9736, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9753, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9758, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9762, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9766, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9770, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9774, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9778, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9783, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9787, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9791, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9795, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9799, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9803, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9807, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9811, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9815, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 5
    ####################################################################
    @staticmethod
    def get_caller_info_s2bo(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded static method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2S",
            func_name="get_caller_info_s2bo",
            line_num=8147,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9844, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9851, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9858, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9875, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9880, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9884, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9888, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9892, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9896, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9900, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9905, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9909, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9913, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9917, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9921, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9925, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9929, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9933, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9937, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 6
    ####################################################################
    @classmethod
    def get_caller_info_c2bo(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded class method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2S",
            func_name="get_caller_info_c2bo",
            line_num=8279,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9966, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9973, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9980, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9997, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10002, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10006, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10010, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10014, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10018, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10022, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10027, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10031, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10035, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10039, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10043, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10047, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10051, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10055, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10059, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 7
    ####################################################################
    def get_caller_info_m2sb(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2S",
            func_name="get_caller_info_m2sb",
            line_num=8410,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10087, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10094, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10101, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call base class normal method target
        update_stack(exp_stack=exp_stack, line_num=10118, add=0)
        self.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=10121, add=0)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10124, add=0)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10128, add=0)
        self.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10130, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10132, add=0)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10134, add=0)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10138, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10140, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10142, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10146, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10151, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10155, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10159, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10163, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10167, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10171, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10176, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10180, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10184, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10188, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10192, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10196, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10200, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10204, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10208, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s2sb(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded static method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2S",
            func_name="get_caller_info_s2sb",
            line_num=8575,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10237, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10244, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10251, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call base class normal method target
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=10269, add=0)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10272, add=0)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10276, add=0)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10278, add=0)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10282, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10284, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10288, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10293, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10297, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10301, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10305, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10309, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10313, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10318, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10322, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10326, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10330, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10334, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10338, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10342, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10346, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10350, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 9
    ####################################################################
    @classmethod
    def get_caller_info_c2sb(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded class method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo2S",
            func_name="get_caller_info_c2sb",
            line_num=8733,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10379, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10386, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10393, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call base class normal method target
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=10411, add=0)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10414, add=0)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10418, add=0)
        cls.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10420, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10422, add=0)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10424, add=0)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10428, add=0)
        cls.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10430, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10432, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10434, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10438, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10443, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10447, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10451, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10455, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10459, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10463, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10468, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10472, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10476, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10480, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10484, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10488, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10492, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10496, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10500, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()


########################################################################
# Class 3
########################################################################
class ClassGetCallerInfo3:
    """Class to get caller info3."""

    def __init__(self) -> None:
        """The initialization."""
        self.var1 = 1

    ####################################################################
    # Class 3 Method 1
    ####################################################################
    def get_caller_info_m3(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        self.var1 += 1
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3",
            func_name="get_caller_info_m3",
            line_num=8911,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10540, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10547, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10554, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 2
    ####################################################################
    @staticmethod
    def get_caller_info_s3(exp_stack: Deque[CallerInfo], capsys: Optional[Any]) -> None:
        """Get caller info static method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3",
            func_name="get_caller_info_s3",
            line_num=8961,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10594, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10601, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10608, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 3
    ####################################################################
    @classmethod
    def get_caller_info_c3(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info class method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output
        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3",
            func_name="get_caller_info_c3",
            line_num=9011,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10649, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10656, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10663, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 4
    ####################################################################
    def get_caller_info_m3bo(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3",
            func_name="get_caller_info_m3bo",
            line_num=9061,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10704, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10711, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10718, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 5
    ####################################################################
    @staticmethod
    def get_caller_info_s3bo(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded static method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3",
            func_name="get_caller_info_s3bo",
            line_num=9111,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10760, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10767, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10774, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 6
    ####################################################################
    @classmethod
    def get_caller_info_c3bo(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded class method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3",
            func_name="get_caller_info_c3bo",
            line_num=9162,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10816, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10823, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10830, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 7
    ####################################################################
    def get_caller_info_m3bt(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        self.var1 += 1
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3",
            func_name="get_caller_info_m3bt",
            line_num=9213,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10872, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10879, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10886, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s3bt(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded static method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3",
            func_name="get_caller_info_s3bt",
            line_num=9263,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10928, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10935, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10942, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 9
    ####################################################################
    @classmethod
    def get_caller_info_c3bt(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded class method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3",
            func_name="get_caller_info_c3bt",
            line_num=9314,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10984, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10991, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10998, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()


########################################################################
# Class 3S
########################################################################
class ClassGetCallerInfo3S(ClassGetCallerInfo3):
    """Subclass to get caller info3."""

    def __init__(self) -> None:
        """The initialization for subclass 3."""
        super().__init__()
        self.var2 = 2

    ####################################################################
    # Class 3S Method 1
    ####################################################################
    def get_caller_info_m3s(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output
        """
        self.var1 += 1
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3S",
            func_name="get_caller_info_m3s",
            line_num=9376,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11051, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11058, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11065, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 2
    ####################################################################
    @staticmethod
    def get_caller_info_s3s(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info static method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3S",
            func_name="get_caller_info_s3s",
            line_num=9426,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11107, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11114, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11121, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 3
    ####################################################################
    @classmethod
    def get_caller_info_c3s(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info class method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3S",
            func_name="get_caller_info_c3s",
            line_num=9477,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11163, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11170, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11177, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 4
    ####################################################################
    def get_caller_info_m3bo(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3S",
            func_name="get_caller_info_m3bo",
            line_num=9527,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11218, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11225, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11232, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 5
    ####################################################################
    @staticmethod
    def get_caller_info_s3bo(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded static method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3S",
            func_name="get_caller_info_s3bo",
            line_num=9577,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11274, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11281, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11288, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 6
    ####################################################################
    @classmethod
    def get_caller_info_c3bo(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded class method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3S",
            func_name="get_caller_info_c3bo",
            line_num=9628,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11330, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11337, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11344, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 7
    ####################################################################
    def get_caller_info_m3sb(
        self, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3S",
            func_name="get_caller_info_m3sb",
            line_num=9678,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11385, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11392, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11399, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call base class normal method target
        update_stack(exp_stack=exp_stack, line_num=11416, add=0)
        self.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=11419, add=0)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11422, add=0)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11426, add=0)
        self.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11428, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11430, add=0)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11432, add=0)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11436, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11438, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11440, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s3sb(
        exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded static method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3S",
            func_name="get_caller_info_s3sb",
            line_num=9762,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11469, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11476, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11483, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call base class normal method target
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=11501, add=0)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11504, add=0)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11508, add=0)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11510, add=0)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11514, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11516, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 9
    ####################################################################
    @classmethod
    def get_caller_info_c3sb(
        cls, exp_stack: Deque[CallerInfo], capsys: Optional[Any]
    ) -> None:
        """Get caller info overloaded class method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="ClassGetCallerInfo3S",
            func_name="get_caller_info_c3sb",
            line_num=9839,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11545, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11552, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11559, add=0)
            before_time = datetime.now()
            diag_msg("message 1", 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack), msg_arg=["message 1", 1]
            )

            verify_diag_msg(
                exp_stack=exp_stack,
                before_time=before_time,
                after_time=after_time,
                capsys=capsys,
                diag_msg_args=diag_msg_args,
            )

        # call base class normal method target
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=11577, add=0)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11580, add=0)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11584, add=0)
        cls.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11586, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11588, add=0)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11590, add=0)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11594, add=0)
        cls.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11596, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11598, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11600, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)

        exp_stack.pop()


########################################################################
# following tests need to be at module level (i.e., script form)
########################################################################

########################################################################
# test get_caller_info from module (script) level
########################################################################
exp_stack0: Deque[CallerInfo] = deque()
exp_caller_info0 = CallerInfo(
    mod_name="test_diag_msg.py", cls_name="", func_name="", line_num=9921
)

exp_stack0.append(exp_caller_info0)
update_stack(exp_stack=exp_stack0, line_num=11622, add=0)
for i0, expected_caller_info0 in enumerate(list(reversed(exp_stack0))):
    try:
        frame0 = _getframe(i0)
        caller_info0 = get_caller_info(frame0)
    finally:
        del frame0
    assert caller_info0 == expected_caller_info0

########################################################################
# test get_formatted_call_sequence from module (script) level
########################################################################
update_stack(exp_stack=exp_stack0, line_num=11631, add=0)
call_seq0 = get_formatted_call_sequence(depth=1)

assert call_seq0 == get_exp_seq(exp_stack=exp_stack0)

########################################################################
# test diag_msg from module (script) level
# note that this is just a smoke test and is only visually verified
########################################################################
diag_msg()  # basic, empty msg
diag_msg("hello")
diag_msg(depth=2)
diag_msg("hello2", depth=3)
diag_msg(depth=4, end="\n\n")
diag_msg("hello3", depth=5, end="\n\n")

# call module level function
update_stack(exp_stack=exp_stack0, line_num=11648, add=0)
func_get_caller_info_1(exp_stack=exp_stack0, capsys=None)

# call method
cls_get_caller_info01 = ClassGetCallerInfo1()
update_stack(exp_stack=exp_stack0, line_num=11653, add=0)
cls_get_caller_info01.get_caller_info_m1(exp_stack=exp_stack0, capsys=None)

# call static method
update_stack(exp_stack=exp_stack0, line_num=11657, add=0)
cls_get_caller_info01.get_caller_info_s1(exp_stack=exp_stack0, capsys=None)

# call class method
update_stack(exp_stack=exp_stack0, line_num=11661, add=0)
ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack0, capsys=None)

# call overloaded base class method
update_stack(exp_stack=exp_stack0, line_num=11665, add=0)
cls_get_caller_info01.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class static method
update_stack(exp_stack=exp_stack0, line_num=11669, add=0)
cls_get_caller_info01.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class class method
update_stack(exp_stack=exp_stack0, line_num=11673, add=0)
ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call subclass method
cls_get_caller_info01S = ClassGetCallerInfo1S()
update_stack(exp_stack=exp_stack0, line_num=11678, add=0)
cls_get_caller_info01S.get_caller_info_m1s(exp_stack=exp_stack0, capsys=None)

# call subclass static method
update_stack(exp_stack=exp_stack0, line_num=11682, add=0)
cls_get_caller_info01S.get_caller_info_s1s(exp_stack=exp_stack0, capsys=None)

# call subclass class method
update_stack(exp_stack=exp_stack0, line_num=11686, add=0)
ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass method
update_stack(exp_stack=exp_stack0, line_num=11690, add=0)
cls_get_caller_info01S.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass static method
update_stack(exp_stack=exp_stack0, line_num=11694, add=0)
cls_get_caller_info01S.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass class method
update_stack(exp_stack=exp_stack0, line_num=11698, add=0)
ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call base method from subclass method
update_stack(exp_stack=exp_stack0, line_num=11702, add=0)
cls_get_caller_info01S.get_caller_info_m1sb(exp_stack=exp_stack0, capsys=None)

# call base static method from subclass static method
update_stack(exp_stack=exp_stack0, line_num=11706, add=0)
cls_get_caller_info01S.get_caller_info_s1sb(exp_stack=exp_stack0, capsys=None)

# call base class method from subclass class method
update_stack(exp_stack=exp_stack0, line_num=11710, add=0)
ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack0, capsys=None)
