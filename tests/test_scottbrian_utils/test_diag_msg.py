"""test_diag_msg.py module."""

from datetime import datetime

import logging

# noinspection PyProtectedMember
from sys import _getframe
import sys  # noqa: F401

from typing import Any, cast, Deque, Final, List, NamedTuple, Optional, Union

# from typing import Text, TypeVar
# from typing_extensions import Final

import pytest
from collections import deque

from scottbrian_utils.diag_msg import get_caller_info
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.diag_msg import diag_msg
from scottbrian_utils.diag_msg import CallerInfo
from scottbrian_utils.diag_msg import diag_msg_datetime_fmt
from scottbrian_utils.diag_msg import get_formatted_call_seq_depth
from scottbrian_utils.diag_msg import diag_msg_caller_depth

from scottbrian_utils.entry_trace import etrace

logger = logging.getLogger(__name__)

########################################################################
# MyPy experiments
########################################################################
# AnyStr = TypeVar('AnyStr', Text, bytes)
#
# def concat(x: AnyStr, y: AnyStr) -> AnyStr:
#     return x + y
#
# x = concat('my', 'pie')
#
# reveal_type(x)
#
# class MyStr(str): ...
#
# x = concat(MyStr('apple'), MyStr('pie'))
#
# reveal_type(x)


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
        update_stack(exp_stack=exp_stack, line_num=536, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=567, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=599, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=602, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=605, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=608, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=617, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=650, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=653, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=656, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=659, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=668, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=703, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=706, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=709, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=712, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=721, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=756, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=759, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=762, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=765, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=792, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=909, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=961, add=0)
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
            update_stack(exp_stack=exp_stack, line_num=964, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=967, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=970, add=0)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=973, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=976, add=0)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=979, add=0)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=982, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=989, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=992, add=2)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=997, add=0)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1000, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1007, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1012, add=4)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1019, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1026, add=5)
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

        update_stack(exp_stack=exp_stack, line_num=1044, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=1076, add=0)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1079, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1082, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1085, add=0)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1088, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1091, add=0)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1094, add=0)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1097, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1104, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1107, add=2)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1112, add=0)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1115, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1122, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1127, add=4)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1134, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1141, add=5)
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

        update_stack(exp_stack=exp_stack, line_num=1159, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=1193, add=0)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1196, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1199, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1202, add=0)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1205, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1208, add=0)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1211, add=0)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1214, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1221, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1224, add=2)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1229, add=0)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1232, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1239, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1244, add=4)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1251, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1258, add=5)
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
    update_stack(exp_stack=exp_stack, line_num=1309, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=1316, add=0)
    call_seq = get_formatted_call_sequence(depth=1)

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    update_stack(exp_stack=exp_stack, line_num=1323, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=1337, add=0)
    func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info1 = ClassGetCallerInfo1()
    update_stack(exp_stack=exp_stack, line_num=1342, add=0)
    cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=1346, add=0)
    cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=1350, add=0)
    ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=1354, add=0)
    cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=1358, add=0)
    cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=1362, add=0)
    ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info1s = ClassGetCallerInfo1S()
    update_stack(exp_stack=exp_stack, line_num=1367, add=0)
    cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=1371, add=0)
    cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=1375, add=0)
    ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=1379, add=0)
    cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=1383, add=0)
    cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=1387, add=0)
    ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=1391, add=0)
    cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=1395, add=0)
    cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=1399, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1430, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1437, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1445, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1461, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1466, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1472, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1478, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1484, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1490, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1496, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1503, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1509, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1515, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1521, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1527, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1533, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1539, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1545, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1551, add=2)
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
            update_stack(exp_stack=exp_stack_g, line_num=1577, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1584, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1592, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1608, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1613, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1619, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1625, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1631, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1637, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1643, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1650, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1656, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1662, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1668, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1674, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1680, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1686, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1692, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1698, add=2)
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
            update_stack(exp_stack=exp_stack_g, line_num=1726, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1733, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1741, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1757, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1762, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1768, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1774, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1780, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1786, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1792, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1799, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1805, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1811, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1817, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1823, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1829, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1835, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1841, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1847, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=1880, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=1887, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=1895, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=1911, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=1916, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=1922, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=1928, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=1934, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=1940, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=1946, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=1953, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1959, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1965, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1971, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1977, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1983, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1989, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1995, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2001, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=2027, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2034, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2042, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2058, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=2063, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2069, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2075, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2081, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2087, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2093, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=2100, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2106, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2112, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2118, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2124, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2130, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2136, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2142, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2148, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=2176, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2183, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2191, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2207, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=2212, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2218, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2224, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2230, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2236, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2242, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=2249, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2255, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2261, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2267, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2273, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2279, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2285, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2291, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2297, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

    a_inner = Inner()
    # call Inner method
    update_stack(exp_stack=exp_stack, line_num=2306, add=0)
    a_inner.g1(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2309, add=0)
    a_inner.g2_static(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2312, add=0)
    a_inner.g3_class(exp_stack_g=exp_stack, capsys_g=capsys)

    a_inherit = Inherit()

    update_stack(exp_stack=exp_stack, line_num=2317, add=0)
    a_inherit.h1(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2320, add=0)
    a_inherit.h2_static(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2323, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=2350, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=2357, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=2365, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=2381, add=0)
    func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info2 = ClassGetCallerInfo2()
    update_stack(exp_stack=exp_stack, line_num=2386, add=0)
    cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=2390, add=0)
    cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=2394, add=0)
    ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=2398, add=0)
    cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=2402, add=0)
    cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=2406, add=0)
    ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info2s = ClassGetCallerInfo2S()
    update_stack(exp_stack=exp_stack, line_num=2411, add=0)
    cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=2415, add=0)
    cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=2419, add=0)
    ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=2423, add=0)
    cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=2427, add=0)
    cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=2431, add=0)
    ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=2435, add=0)
    cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=2439, add=0)
    cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=2443, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2474, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2481, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2489, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2505, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2510, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2516, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2522, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2528, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2534, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2540, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2547, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2553, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2559, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2565, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2571, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2577, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2583, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2589, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2595, add=2)
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
            update_stack(exp_stack=exp_stack_g, line_num=2621, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2628, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2636, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2652, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2657, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2663, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2669, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2675, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2681, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2687, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2694, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2700, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2706, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2712, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2718, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2724, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2730, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2736, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2742, add=2)
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
            update_stack(exp_stack=exp_stack_g, line_num=2770, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2777, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2785, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2801, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2806, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2812, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2818, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2824, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2830, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2836, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2843, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2849, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2855, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2861, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2867, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2873, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2879, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2885, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2891, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=2924, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2931, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2939, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2955, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2960, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2966, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2972, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2978, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2984, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2990, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=2997, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3003, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3009, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3015, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3021, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3027, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3033, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3039, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3045, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=3071, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=3078, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=3086, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=3102, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=3107, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=3113, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=3119, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=3125, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=3131, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=3137, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=3144, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3150, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3156, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3162, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3168, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3174, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3180, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3186, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3192, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=3220, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=3227, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=3235, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=3251, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=3256, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=3262, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=3268, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=3274, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=3280, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=3286, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=3293, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3299, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3305, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3311, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3317, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3323, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3329, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3335, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3341, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

    a_inner = Inner()
    # call Inner method
    update_stack(exp_stack=exp_stack, line_num=3350, add=0)
    a_inner.g1(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=3353, add=0)
    a_inner.g2_static(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=3356, add=0)
    a_inner.g3_class(exp_stack_g=exp_stack, capsys_g=capsys)

    a_inherit = Inherit()

    update_stack(exp_stack=exp_stack, line_num=3361, add=0)
    a_inherit.h1(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=3364, add=0)
    a_inherit.h2_static(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=3367, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=3394, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=3401, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3409, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=3425, add=0)
    func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info3 = ClassGetCallerInfo3()
    update_stack(exp_stack=exp_stack, line_num=3430, add=0)
    cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=3434, add=0)
    cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=3438, add=0)
    ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=3442, add=0)
    cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=3446, add=0)
    cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=3450, add=0)
    ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info3s = ClassGetCallerInfo3S()
    update_stack(exp_stack=exp_stack, line_num=3455, add=0)
    cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=3459, add=0)
    cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=3463, add=0)
    ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=3467, add=0)
    cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=3471, add=0)
    cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=3475, add=0)
    ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=3479, add=0)
    cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=3483, add=0)
    cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=3487, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=3514, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=3521, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3529, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3577, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3584, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3591, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3607, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3612, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3616, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3620, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3624, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3628, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3632, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3637, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3641, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3645, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3649, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3653, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3657, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3661, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3665, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3669, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3692, add=0)
        self.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3694, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)

        update_stack(exp_stack=exp_stack, line_num=3697, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3699, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3723, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3730, add=0)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3737, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3753, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3758, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3762, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3766, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3770, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3774, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3778, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3783, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3787, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3791, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3795, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3799, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3803, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3807, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3811, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3815, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3841, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3848, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3855, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3871, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3876, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3880, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3884, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3888, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3892, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3896, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3901, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3905, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3909, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3913, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3917, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3921, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3925, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3929, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3933, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3959, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3966, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3973, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3989, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3994, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3998, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4002, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4006, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4010, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4014, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4019, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4023, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4027, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4031, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4035, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4039, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4043, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4047, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4051, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4078, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4085, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4092, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4108, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4113, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4117, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4121, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4125, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4129, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4133, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4138, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4142, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4146, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4150, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4154, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4158, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4162, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4166, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4170, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4197, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4204, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4211, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4227, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4232, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4236, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4240, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4244, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4248, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4252, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4257, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4261, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4265, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4269, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4273, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4277, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4281, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4285, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4289, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4315, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4322, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4329, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4345, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4350, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4354, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4358, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4362, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4366, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4370, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4375, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4379, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4383, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4387, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4391, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4395, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4399, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4403, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4407, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4436, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4443, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4450, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4466, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4471, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4475, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4479, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4483, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4487, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4491, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4496, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4500, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4504, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4508, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4512, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4516, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4520, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4524, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4528, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4555, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4562, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4569, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4585, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4590, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4594, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4598, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4602, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4606, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4610, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4615, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4619, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4623, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4627, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4631, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4635, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4639, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4643, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4647, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4678, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4685, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4692, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4708, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4713, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4717, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4721, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4725, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4729, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4733, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4738, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4742, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4746, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4750, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4754, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4758, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4762, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4766, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4770, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4802, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4809, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4816, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4832, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4837, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4841, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4845, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4849, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4853, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4857, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4862, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4866, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4870, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4874, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4878, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4882, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4886, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4890, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4894, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4921, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4928, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4935, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4951, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4956, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4960, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4964, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4968, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4972, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4976, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4981, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4985, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4989, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4993, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4997, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5001, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5005, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5009, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5013, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5040, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5047, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5054, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5070, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5075, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5079, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5083, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5087, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5091, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5095, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5100, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5104, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5108, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5112, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5116, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5120, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5124, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5128, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5132, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5158, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5165, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5172, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5188, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5193, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5197, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5201, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5205, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5209, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5213, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5218, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5222, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5226, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5230, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5234, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5238, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5242, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5246, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5250, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5277, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5284, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5291, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5307, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5312, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5316, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5320, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5324, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5328, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5332, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5337, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5341, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5345, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5349, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5353, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5357, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5361, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5365, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5369, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5396, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5403, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5410, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5426, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5431, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5435, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5439, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5443, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5447, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5451, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5456, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5460, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5464, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5468, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5472, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5476, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5480, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5484, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5488, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5514, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5521, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5528, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5544, add=0)
        self.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        update_stack(exp_stack=exp_stack, line_num=5547, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5550, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5554, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5556, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5558, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5560, add=2)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5566, add=0)
        super().get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5568, add=0)
        TestClassGetCallerInfo0.get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5570, add=2)
        TestClassGetCallerInfo0S.get_caller_info_c0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5576, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5581, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5585, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5589, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5593, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5597, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5601, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5606, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5610, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5614, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5618, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5622, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5626, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5630, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5634, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5638, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5665, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5672, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5679, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5696, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5699, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5703, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5705, add=2)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5711, add=0)
        TestClassGetCallerInfo0.get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5713, add=2)
        TestClassGetCallerInfo0S.get_caller_info_c0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5719, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5724, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5728, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5732, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5736, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5740, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5744, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5749, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5753, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5757, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5761, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5765, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5769, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5773, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5777, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5781, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5808, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5815, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5822, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5839, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5842, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5846, add=0)
        cls.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5848, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5850, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5852, add=2)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )
        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5857, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5862, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5866, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5870, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5874, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5878, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5882, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5887, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5891, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5895, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5899, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5903, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5907, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5911, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5915, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5919, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5959, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5966, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=5973, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5990, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=5995, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5999, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6003, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6007, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6011, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6015, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6020, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6024, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6028, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6032, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6036, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6040, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6044, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6048, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6052, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6079, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6086, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6093, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6110, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6115, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6119, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6123, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6127, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6131, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6135, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6140, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6144, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6148, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6152, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6156, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6160, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6164, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6168, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6172, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6200, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6207, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6214, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6231, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6236, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6240, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6244, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6248, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6252, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6256, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6261, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6265, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6269, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6273, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6277, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6281, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6285, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6289, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6293, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6321, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6328, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6335, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6352, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6357, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6361, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6365, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6369, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6373, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6377, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6382, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6386, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6390, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6394, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6398, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6402, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6406, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6410, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6414, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6443, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6450, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6457, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6474, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6479, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6483, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6487, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6491, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6495, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6499, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6504, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6508, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6512, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6516, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6520, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6524, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6528, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6532, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6536, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6565, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6572, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6579, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6596, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6601, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6605, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6609, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6613, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6617, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6621, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6626, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6630, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6634, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6638, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6642, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6646, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6650, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6654, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6658, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6687, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6694, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6701, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6718, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6723, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6727, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6731, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6735, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6739, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6743, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6748, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6752, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6756, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6760, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6764, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6768, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6772, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6776, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6780, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6809, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6816, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6823, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6840, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6845, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6849, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6853, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6857, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6861, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6865, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6870, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6874, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6878, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6882, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6886, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6890, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6894, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6898, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6902, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6931, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6938, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6945, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6962, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6967, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6971, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6975, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6979, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6983, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6987, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6992, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6996, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7000, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7004, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7008, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7012, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7016, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7020, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7024, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7064, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7071, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7078, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7095, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7100, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7104, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7108, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7112, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7116, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7120, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7125, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7129, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7133, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7137, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7141, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7145, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7149, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7153, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7157, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7186, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7193, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7200, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7217, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7222, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7226, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7230, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7234, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7238, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7242, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7247, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7251, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7255, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7259, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7263, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7267, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7271, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7275, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7279, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7308, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7315, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7322, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7339, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7344, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7348, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7352, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7356, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7360, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7364, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7369, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7373, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7377, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7381, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7385, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7389, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7393, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7397, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7401, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7429, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7436, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7443, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7460, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7465, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7469, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7473, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7477, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7481, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7485, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7490, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7494, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7498, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7502, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7506, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7510, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7514, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7518, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7522, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7551, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7558, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7565, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7582, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7587, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7591, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7595, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7599, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7603, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7607, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7612, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7616, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7620, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7624, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7628, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7632, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7636, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7640, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7644, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7673, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7680, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7687, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7704, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7709, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7713, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7717, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7721, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7725, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7729, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7734, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7738, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7742, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7746, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7750, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7754, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7758, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7762, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7766, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7794, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7801, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7808, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7825, add=0)
        self.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=7828, add=0)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7831, add=0)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7835, add=0)
        self.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7837, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7839, add=0)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7841, add=0)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7845, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7847, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7849, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7853, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7858, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7862, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7866, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7870, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7874, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7878, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7883, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7887, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7891, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7895, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7899, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7903, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7907, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7911, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7915, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7944, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7951, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7958, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7976, add=0)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7979, add=0)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7983, add=0)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7985, add=0)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7989, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7991, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7995, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=8000, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8004, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8008, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8012, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8016, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8020, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=8025, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8029, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8033, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8037, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8041, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8045, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8049, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8053, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8057, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8086, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8093, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8100, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8118, add=0)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=8121, add=0)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=8125, add=0)
        cls.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8127, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8129, add=0)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8131, add=0)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=8135, add=0)
        cls.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8137, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8139, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8141, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8145, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=8150, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8154, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8158, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8162, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8166, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8170, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=8175, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8179, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8183, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8187, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8191, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8195, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8199, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8203, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8207, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8247, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8254, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8261, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8278, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8283, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8287, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8291, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8295, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8299, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8303, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8308, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8312, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8316, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8320, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8324, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8328, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8332, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8336, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8340, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8367, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8374, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8381, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8398, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8403, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8407, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8411, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8415, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8419, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8423, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8428, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8432, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8436, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8440, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8444, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8448, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8452, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8456, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8460, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8488, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8495, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8502, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8519, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8524, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8528, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8532, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8536, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8540, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8544, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8549, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8553, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8557, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8561, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8565, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8569, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8573, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8577, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8581, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8609, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8616, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8623, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8640, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8645, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8649, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8653, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8657, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8661, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8665, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8670, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8674, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8678, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8682, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8686, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8690, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8694, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8698, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8702, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8731, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8738, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8745, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8762, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8767, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8771, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8775, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8779, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8783, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8787, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8792, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8796, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8800, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8804, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8808, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8812, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8816, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8820, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8824, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8853, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8860, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8867, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8884, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8889, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8893, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8897, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8901, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8905, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8909, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8914, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8918, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8922, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8926, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8930, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8934, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8938, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8942, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8946, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8975, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8982, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8989, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9006, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9011, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9015, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9019, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9023, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9027, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9031, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9036, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9040, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9044, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9048, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9052, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9056, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9060, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9064, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9068, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9097, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9104, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9111, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9128, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9133, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9137, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9141, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9145, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9149, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9153, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9158, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9162, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9166, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9170, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9174, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9178, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9182, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9186, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9190, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9219, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9226, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9233, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9250, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9255, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9259, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9263, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9267, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9271, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9275, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9280, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9284, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9288, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9292, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9296, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9300, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9304, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9308, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9312, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9352, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9359, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9366, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9383, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9388, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9392, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9396, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9400, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9404, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9408, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9413, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9417, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9421, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9425, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9429, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9433, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9437, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9441, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9445, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9474, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9481, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9488, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9505, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9510, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9514, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9518, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9522, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9526, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9530, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9535, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9539, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9543, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9547, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9551, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9555, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9559, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9563, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9567, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9596, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9603, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9610, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9627, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9632, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9636, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9640, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9644, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9648, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9652, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9657, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9661, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9665, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9669, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9673, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9677, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9681, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9685, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9689, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9717, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9724, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9731, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9748, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9753, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9757, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9761, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9765, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9769, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9773, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9778, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9782, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9786, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9790, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9794, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9798, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9802, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9806, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9810, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9839, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9846, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9853, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9870, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9875, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9879, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9883, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9887, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9891, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9895, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9900, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9904, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9908, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9912, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9916, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9920, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9924, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9928, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9932, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9961, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9968, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9975, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9992, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9997, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10001, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10005, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10009, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10013, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10017, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10022, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10026, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10030, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10034, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10038, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10042, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10046, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10050, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10054, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10082, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10089, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10096, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10113, add=0)
        self.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=10116, add=0)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10119, add=0)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10123, add=0)
        self.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10125, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10127, add=0)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10129, add=0)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10133, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10135, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10137, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10141, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10146, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10150, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10154, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10158, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10162, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10166, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10171, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10175, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10179, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10183, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10187, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10191, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10195, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10199, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10203, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10232, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10239, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10246, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10264, add=0)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10267, add=0)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10271, add=0)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10273, add=0)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10277, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10279, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10283, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10288, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10292, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10296, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10300, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10304, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10308, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10313, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10317, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10321, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10325, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10329, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10333, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10337, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10341, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10345, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10374, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10381, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10388, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10406, add=0)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10409, add=0)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10413, add=0)
        cls.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10415, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10417, add=0)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10419, add=0)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10423, add=0)
        cls.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10425, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10427, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10429, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10433, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10438, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10442, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10446, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10450, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10454, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10458, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10463, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10467, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10471, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10475, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10479, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10483, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10487, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10491, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10495, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10535, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10542, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10549, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10589, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10596, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10603, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10644, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10651, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10658, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10699, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10706, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10713, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10755, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10762, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10769, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10811, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10818, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10825, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10867, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10874, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10881, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10923, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10930, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10937, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10979, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10986, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10993, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11046, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11053, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11060, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11102, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11109, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11116, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11158, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11165, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11172, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11213, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11220, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11227, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11269, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11276, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11283, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11325, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11332, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11339, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11380, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11387, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11394, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11411, add=0)
        self.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=11414, add=0)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11417, add=0)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11421, add=0)
        self.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11423, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11425, add=0)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11427, add=0)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11431, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11433, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11435, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11464, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11471, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11478, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11496, add=0)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11499, add=0)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11503, add=0)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11505, add=0)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11509, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11511, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11540, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11547, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11554, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11572, add=0)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11575, add=0)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11579, add=0)
        cls.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11581, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11583, add=0)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11585, add=0)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11589, add=0)
        cls.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11591, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11593, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11595, add=0)
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
update_stack(exp_stack=exp_stack0, line_num=11617, add=0)
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
update_stack(exp_stack=exp_stack0, line_num=11626, add=0)
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
update_stack(exp_stack=exp_stack0, line_num=11643, add=0)
func_get_caller_info_1(exp_stack=exp_stack0, capsys=None)

# call method
cls_get_caller_info01 = ClassGetCallerInfo1()
update_stack(exp_stack=exp_stack0, line_num=11648, add=0)
cls_get_caller_info01.get_caller_info_m1(exp_stack=exp_stack0, capsys=None)

# call static method
update_stack(exp_stack=exp_stack0, line_num=11652, add=0)
cls_get_caller_info01.get_caller_info_s1(exp_stack=exp_stack0, capsys=None)

# call class method
update_stack(exp_stack=exp_stack0, line_num=11656, add=0)
ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack0, capsys=None)

# call overloaded base class method
update_stack(exp_stack=exp_stack0, line_num=11660, add=0)
cls_get_caller_info01.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class static method
update_stack(exp_stack=exp_stack0, line_num=11664, add=0)
cls_get_caller_info01.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class class method
update_stack(exp_stack=exp_stack0, line_num=11668, add=0)
ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call subclass method
cls_get_caller_info01S = ClassGetCallerInfo1S()
update_stack(exp_stack=exp_stack0, line_num=11673, add=0)
cls_get_caller_info01S.get_caller_info_m1s(exp_stack=exp_stack0, capsys=None)

# call subclass static method
update_stack(exp_stack=exp_stack0, line_num=11677, add=0)
cls_get_caller_info01S.get_caller_info_s1s(exp_stack=exp_stack0, capsys=None)

# call subclass class method
update_stack(exp_stack=exp_stack0, line_num=11681, add=0)
ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass method
update_stack(exp_stack=exp_stack0, line_num=11685, add=0)
cls_get_caller_info01S.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass static method
update_stack(exp_stack=exp_stack0, line_num=11689, add=0)
cls_get_caller_info01S.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass class method
update_stack(exp_stack=exp_stack0, line_num=11693, add=0)
ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call base method from subclass method
update_stack(exp_stack=exp_stack0, line_num=11697, add=0)
cls_get_caller_info01S.get_caller_info_m1sb(exp_stack=exp_stack0, capsys=None)

# call base static method from subclass static method
update_stack(exp_stack=exp_stack0, line_num=11701, add=0)
cls_get_caller_info01S.get_caller_info_s1sb(exp_stack=exp_stack0, capsys=None)

# call base class method from subclass class method
update_stack(exp_stack=exp_stack0, line_num=11705, add=0)
ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack0, capsys=None)
