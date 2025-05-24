"""test_diag_msg.py module."""

from datetime import datetime

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

    assert call_seq == seq_slice(call_seq=call_seq, end=seq_depth)

    if seq_latest is None:
        seq_latest = 0

    # if we have enough stack entries to test
    if seq_latest < len(exp_stack):
        if len(exp_stack) - seq_latest < seq_depth:  # if need to slice
            call_seq = seq_slice(call_seq=call_seq, end=len(exp_stack) - seq_latest)

        if len(exp_stack) <= seq_latest + seq_depth:
            assert call_seq == get_exp_seq(exp_stack=exp_stack, latest=seq_latest)
        else:
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
        update_stack(exp_stack=exp_stack, line_num=509, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=540, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=572, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=575, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=578, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=581, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=590, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=623, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=626, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=629, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=632, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=641, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=676, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=679, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=682, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=685, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=694, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=729, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=732, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=735, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=738, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=765, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=882, add=0)
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
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(
            mod_name="test_diag_msg.py",
            cls_name="TestDiagMsg",
            func_name="test_diag_msg_with_parms",
            line_num=768,
        )
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=932, add=0)
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
            update_stack(exp_stack=exp_stack, line_num=935, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=938, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=941, add=0)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=944, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=947, add=0)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=950, add=0)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=953, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=960, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=963, add=2)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=968, add=0)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=971, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=978, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=983, add=4)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=990, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=997, add=5)
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

        update_stack(exp_stack=exp_stack, line_num=1015, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=1047, add=0)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1050, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1053, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1056, add=0)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1059, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1062, add=0)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1065, add=0)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1068, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1075, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1078, add=2)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1083, add=0)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1086, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1093, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1098, add=4)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1105, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1112, add=5)
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

        update_stack(exp_stack=exp_stack, line_num=1130, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=1164, add=0)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1167, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1170, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1173, add=0)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1176, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1179, add=0)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1182, add=0)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1185, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1192, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1195, add=2)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1200, add=0)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1203, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1210, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1215, add=4)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1222, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1229, add=5)
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
    update_stack(exp_stack=exp_stack, line_num=1280, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=1287, add=0)
    call_seq = get_formatted_call_sequence(depth=1)

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    update_stack(exp_stack=exp_stack, line_num=1294, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=1308, add=0)
    func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info1 = ClassGetCallerInfo1()
    update_stack(exp_stack=exp_stack, line_num=1313, add=0)
    cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=1317, add=0)
    cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=1321, add=0)
    ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=1325, add=0)
    cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=1329, add=0)
    cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=1333, add=0)
    ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info1s = ClassGetCallerInfo1S()
    update_stack(exp_stack=exp_stack, line_num=1338, add=0)
    cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=1342, add=0)
    cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=1346, add=0)
    ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=1350, add=0)
    cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=1354, add=0)
    cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=1358, add=0)
    ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=1362, add=0)
    cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=1366, add=0)
    cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=1370, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1401, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1408, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1416, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1432, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1437, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1443, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1449, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1455, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1461, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1467, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1474, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1480, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1486, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1492, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1498, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1504, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1510, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1516, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1522, add=2)
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
            update_stack(exp_stack=exp_stack_g, line_num=1548, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1555, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1563, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1579, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1584, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1590, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1596, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1602, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1608, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1614, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1621, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1627, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1633, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1639, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1645, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1651, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1657, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1663, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1669, add=2)
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
            update_stack(exp_stack=exp_stack_g, line_num=1697, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1704, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1712, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1728, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1733, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1739, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1745, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1751, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1757, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1763, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1770, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1776, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1782, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1788, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1794, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1800, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1806, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1812, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1818, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=1851, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=1858, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=1866, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=1882, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=1887, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=1893, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=1899, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=1905, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=1911, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=1917, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=1924, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1930, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1936, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1942, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1948, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1954, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1960, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1966, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1972, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=1998, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2005, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2013, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2029, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=2034, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2040, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2046, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2052, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2058, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2064, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=2071, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2077, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2083, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2089, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2095, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2101, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2107, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2113, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2119, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=2147, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2154, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2162, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2178, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=2183, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2189, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2195, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2201, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2207, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2213, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=2220, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2226, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2232, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2238, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2244, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2250, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2256, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2262, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2268, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

    a_inner = Inner()
    # call Inner method
    update_stack(exp_stack=exp_stack, line_num=2277, add=0)
    a_inner.g1(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2280, add=0)
    a_inner.g2_static(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2283, add=0)
    a_inner.g3_class(exp_stack_g=exp_stack, capsys_g=capsys)

    a_inherit = Inherit()

    update_stack(exp_stack=exp_stack, line_num=2288, add=0)
    a_inherit.h1(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2291, add=0)
    a_inherit.h2_static(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2294, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=2321, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=2328, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=2336, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=2352, add=0)
    func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info2 = ClassGetCallerInfo2()
    update_stack(exp_stack=exp_stack, line_num=2357, add=0)
    cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=2361, add=0)
    cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=2365, add=0)
    ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=2369, add=0)
    cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=2373, add=0)
    cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=2377, add=0)
    ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info2s = ClassGetCallerInfo2S()
    update_stack(exp_stack=exp_stack, line_num=2382, add=0)
    cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=2386, add=0)
    cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=2390, add=0)
    ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=2394, add=0)
    cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=2398, add=0)
    cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=2402, add=0)
    ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=2406, add=0)
    cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=2410, add=0)
    cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=2414, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2445, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2452, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2460, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2476, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2481, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2487, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2493, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2499, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2505, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2511, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2518, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2524, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2530, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2536, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2542, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2548, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2554, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2560, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2566, add=2)
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
            update_stack(exp_stack=exp_stack_g, line_num=2592, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2599, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2607, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2623, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2628, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2634, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2640, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2646, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2652, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2658, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2665, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2671, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2677, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2683, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2689, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2695, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2701, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2707, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2713, add=2)
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
            update_stack(exp_stack=exp_stack_g, line_num=2741, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2748, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2756, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2772, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2777, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2783, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2789, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2795, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2801, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2807, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2814, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2820, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2826, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2832, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2838, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2844, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2850, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2856, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2862, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=2895, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2902, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2910, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2926, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2931, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2937, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2943, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2949, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2955, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2961, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=2968, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2974, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2980, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2986, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2992, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2998, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3004, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3010, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3016, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=3042, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=3049, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=3057, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=3073, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=3078, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=3084, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=3090, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=3096, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=3102, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=3108, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=3115, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3121, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3127, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3133, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3139, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3145, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3151, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3157, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3163, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=3191, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=3198, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=3206, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=3222, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=3227, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=3233, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=3239, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=3245, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=3251, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=3257, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=3264, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3270, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3276, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3282, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3288, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3294, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3300, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3306, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3312, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

    a_inner = Inner()
    # call Inner method
    update_stack(exp_stack=exp_stack, line_num=3321, add=0)
    a_inner.g1(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=3324, add=0)
    a_inner.g2_static(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=3327, add=0)
    a_inner.g3_class(exp_stack_g=exp_stack, capsys_g=capsys)

    a_inherit = Inherit()

    update_stack(exp_stack=exp_stack, line_num=3332, add=0)
    a_inherit.h1(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=3335, add=0)
    a_inherit.h2_static(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=3338, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=3365, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=3372, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3380, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=3396, add=0)
    func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info3 = ClassGetCallerInfo3()
    update_stack(exp_stack=exp_stack, line_num=3401, add=0)
    cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=3405, add=0)
    cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=3409, add=0)
    ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=3413, add=0)
    cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=3417, add=0)
    cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=3421, add=0)
    ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info3s = ClassGetCallerInfo3S()
    update_stack(exp_stack=exp_stack, line_num=3426, add=0)
    cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=3430, add=0)
    cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=3434, add=0)
    ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=3438, add=0)
    cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=3442, add=0)
    cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=3446, add=0)
    ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=3450, add=0)
    cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=3454, add=0)
    cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=3458, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=3485, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=3492, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3500, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3548, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3555, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3562, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3578, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3583, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3587, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3591, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3595, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3599, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3603, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3608, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3612, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3616, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3620, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3624, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3628, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3632, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3636, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3640, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3663, add=0)
        self.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3665, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)

        update_stack(exp_stack=exp_stack, line_num=3668, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3670, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3694, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3701, add=0)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3708, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3724, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3729, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3733, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3737, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3741, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3745, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3749, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3754, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3758, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3762, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3766, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3770, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3774, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3778, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3782, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3786, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3812, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3819, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3826, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3842, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3847, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3851, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3855, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3859, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3863, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3867, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3872, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3876, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3880, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3884, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3888, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3892, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3896, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3900, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3904, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3930, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3937, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3944, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3960, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3965, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3969, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3973, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3977, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3981, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3985, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3990, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3994, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3998, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4002, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4006, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4010, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4014, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4018, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4022, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4049, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4056, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4063, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4079, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4084, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4088, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4092, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4096, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4100, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4104, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4109, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4113, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4117, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4121, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4125, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4129, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4133, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4137, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4141, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4168, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4175, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4182, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4198, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4203, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4207, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4211, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4215, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4219, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4223, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4228, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4232, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4236, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4240, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4244, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4248, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4252, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4256, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4260, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4286, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4293, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4300, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4316, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4321, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4325, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4329, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4333, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4337, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4341, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4346, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4350, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4354, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4358, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4362, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4366, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4370, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4374, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4378, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4407, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4414, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4421, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4437, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4442, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4446, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4450, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4454, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4458, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4462, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4467, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4471, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4475, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4479, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4483, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4487, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4491, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4495, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4499, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4526, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4533, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4540, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4556, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4561, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4565, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4569, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4573, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4577, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4581, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4586, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4590, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4594, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4598, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4602, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4606, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4610, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4614, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4618, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4649, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4656, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4663, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4679, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4684, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4688, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4692, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4696, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4700, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4704, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4709, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4713, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4717, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4721, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4725, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4729, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4733, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4737, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4741, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4773, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4780, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4787, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4803, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4808, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4812, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4816, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4820, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4824, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4828, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4833, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4837, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4841, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4845, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4849, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4853, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4857, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4861, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4865, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4892, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4899, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4906, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4922, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4927, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4931, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4935, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4939, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4943, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4947, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4952, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4956, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4960, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4964, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4968, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4972, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4976, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4980, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4984, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5011, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5018, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5025, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5041, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5046, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5050, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5054, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5058, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5062, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5066, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5071, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5075, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5079, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5083, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5087, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5091, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5095, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5099, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5103, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5129, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5136, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5143, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5159, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5164, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5168, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5172, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5176, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5180, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5184, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5189, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5193, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5197, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5201, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5205, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5209, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5213, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5217, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5221, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5248, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5255, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5262, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5278, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5283, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5287, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5291, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5295, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5299, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5303, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5308, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5312, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5316, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5320, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5324, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5328, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5332, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5336, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5340, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5367, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5374, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5381, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5397, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5402, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5406, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5410, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5414, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5418, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5422, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5427, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5431, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5435, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5439, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5443, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5447, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5451, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5455, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5459, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5485, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5492, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5499, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5515, add=0)
        self.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        update_stack(exp_stack=exp_stack, line_num=5518, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5521, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5525, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5527, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5529, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5531, add=2)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5537, add=0)
        super().get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5539, add=0)
        TestClassGetCallerInfo0.get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5541, add=2)
        TestClassGetCallerInfo0S.get_caller_info_c0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5547, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5552, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5556, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5560, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5564, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5568, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5572, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5577, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5581, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5585, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5589, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5593, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5597, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5601, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5605, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5609, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5636, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5643, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5650, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5667, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5670, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5674, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5676, add=2)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5682, add=0)
        TestClassGetCallerInfo0.get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5684, add=2)
        TestClassGetCallerInfo0S.get_caller_info_c0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5690, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5695, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5699, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5703, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5707, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5711, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5715, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5720, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5724, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5728, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5732, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5736, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5740, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5744, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5748, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5752, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5779, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5786, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5793, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5810, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5813, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5817, add=0)
        cls.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5819, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5821, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5823, add=2)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )
        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5828, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5833, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5837, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5841, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5845, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5849, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5853, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5858, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5862, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5866, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5870, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5874, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5878, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5882, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5886, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5890, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5930, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5937, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=5944, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5961, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=5966, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5970, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5974, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5978, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5982, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5986, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=5991, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5995, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5999, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6003, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6007, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6011, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6015, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6019, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6023, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6050, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6057, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6064, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6081, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6086, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6090, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6094, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6098, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6102, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6106, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6111, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6115, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6119, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6123, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6127, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6131, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6135, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6139, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6143, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6171, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6178, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6185, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6202, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6207, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6211, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6215, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6219, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6223, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6227, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6232, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6236, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6240, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6244, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6248, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6252, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6256, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6260, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6264, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6292, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6299, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6306, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6323, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6328, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6332, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6336, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6340, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6344, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6348, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6353, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6357, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6361, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6365, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6369, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6373, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6377, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6381, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6385, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6414, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6421, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6428, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6445, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6450, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6454, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6458, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6462, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6466, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6470, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6475, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6479, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6483, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6487, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6491, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6495, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6499, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6503, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6507, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6536, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6543, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6550, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6567, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6572, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6576, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6580, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6584, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6588, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6592, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6597, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6601, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6605, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6609, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6613, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6617, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6621, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6625, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6629, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6658, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6665, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6672, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6689, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6694, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6698, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6702, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6706, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6710, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6714, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6719, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6723, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6727, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6731, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6735, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6739, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6743, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6747, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6751, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6780, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6787, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6794, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6811, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6816, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6820, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6824, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6828, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6832, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6836, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6841, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6845, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6849, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6853, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6857, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6861, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6865, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6869, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6873, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6902, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6909, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6916, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6933, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6938, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6942, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6946, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6950, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6954, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6958, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6963, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6967, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6971, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6975, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6979, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6983, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6987, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6991, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6995, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7035, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7042, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7049, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7066, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7071, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7075, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7079, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7083, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7087, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7091, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7096, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7100, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7104, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7108, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7112, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7116, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7120, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7124, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7128, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7157, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7164, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7171, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7188, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7193, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7197, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7201, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7205, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7209, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7213, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7218, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7222, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7226, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7230, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7234, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7238, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7242, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7246, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7250, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7279, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7286, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7293, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7310, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7315, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7319, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7323, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7327, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7331, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7335, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7340, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7344, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7348, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7352, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7356, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7360, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7364, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7368, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7372, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7400, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7407, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7414, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7431, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7436, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7440, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7444, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7448, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7452, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7456, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7461, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7465, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7469, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7473, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7477, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7481, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7485, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7489, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7493, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7522, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7529, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7536, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7553, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7558, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7562, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7566, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7570, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7574, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7578, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7583, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7587, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7591, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7595, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7599, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7603, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7607, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7611, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7615, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7644, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7651, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7658, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7675, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7680, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7684, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7688, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7692, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7696, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7700, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7705, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7709, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7713, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7717, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7721, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7725, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7729, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7733, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7737, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7765, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7772, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7779, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7796, add=0)
        self.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=7799, add=0)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7802, add=0)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7806, add=0)
        self.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7808, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7810, add=0)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7812, add=0)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7816, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7818, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7820, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7824, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7829, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7833, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7837, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7841, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7845, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7849, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7854, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7858, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7862, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7866, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7870, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7874, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7878, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7882, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7886, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7915, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7922, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7929, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7947, add=0)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7950, add=0)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7954, add=0)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7956, add=0)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7960, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7962, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7966, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7971, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7975, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7979, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7983, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7987, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7991, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7996, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8000, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8004, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8008, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8012, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8016, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8020, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8024, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8028, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8057, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8064, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8071, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8089, add=0)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=8092, add=0)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=8096, add=0)
        cls.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8098, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8100, add=0)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8102, add=0)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=8106, add=0)
        cls.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8108, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8110, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8112, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8116, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=8121, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8125, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8129, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8133, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8137, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8141, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=8146, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8150, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8154, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8158, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8162, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8166, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8170, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8174, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8178, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8218, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8225, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8232, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8249, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8254, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8258, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8262, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8266, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8270, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8274, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8279, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8283, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8287, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8291, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8295, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8299, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8303, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8307, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8311, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8338, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8345, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8352, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8369, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8374, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8378, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8382, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8386, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8390, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8394, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8399, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8403, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8407, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8411, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8415, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8419, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8423, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8427, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8431, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8459, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8466, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8473, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8490, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8495, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8499, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8503, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8507, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8511, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8515, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8520, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8524, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8528, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8532, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8536, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8540, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8544, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8548, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8552, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8580, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8587, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8594, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8611, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8616, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8620, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8624, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8628, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8632, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8636, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8641, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8645, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8649, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8653, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8657, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8661, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8665, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8669, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8673, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8702, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8709, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8716, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8733, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8738, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8742, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8746, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8750, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8754, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8758, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8763, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8767, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8771, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8775, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8779, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8783, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8787, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8791, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8795, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8824, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8831, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8838, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8855, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8860, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8864, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8868, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8872, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8876, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8880, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8885, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8889, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8893, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8897, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8901, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8905, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8909, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8913, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8917, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8946, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8953, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8960, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8977, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8982, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8986, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8990, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8994, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8998, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9002, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9007, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9011, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9015, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9019, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9023, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9027, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9031, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9035, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9039, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9068, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9075, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9082, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9099, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9104, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9108, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9112, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9116, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9120, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9124, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9129, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9133, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9137, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9141, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9145, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9149, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9153, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9157, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9161, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9190, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9197, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9204, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9221, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9226, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9230, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9234, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9238, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9242, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9246, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9251, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9255, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9259, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9263, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9267, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9271, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9275, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9279, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9283, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9323, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9330, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9337, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9354, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9359, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9363, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9367, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9371, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9375, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9379, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9384, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9388, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9392, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9396, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9400, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9404, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9408, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9412, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9416, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9445, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9452, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9459, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9476, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9481, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9485, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9489, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9493, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9497, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9501, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9506, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9510, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9514, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9518, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9522, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9526, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9530, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9534, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9538, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9567, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9574, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9581, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9598, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9603, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9607, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9611, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9615, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9619, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9623, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9628, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9632, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9636, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9640, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9644, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9648, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9652, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9656, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9660, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9688, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9695, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9702, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9719, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9724, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9728, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9732, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9736, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9740, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9744, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9749, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9753, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9757, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9761, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9765, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9769, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9773, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9777, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9781, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9810, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9817, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9824, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9841, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9846, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9850, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9854, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9858, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9862, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9866, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9871, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9875, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9879, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9883, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9887, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9891, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9895, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9899, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9903, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9932, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9939, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9946, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9963, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9968, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9972, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9976, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9980, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9984, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9988, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9993, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9997, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10001, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10005, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10009, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10013, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10017, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10021, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10025, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10053, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10060, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10067, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10084, add=0)
        self.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=10087, add=0)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10090, add=0)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10094, add=0)
        self.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10096, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10098, add=0)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10100, add=0)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10104, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10106, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10108, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10112, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10117, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10121, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10125, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10129, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10133, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10137, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10142, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10146, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10150, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10154, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10158, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10162, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10166, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10170, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10174, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10203, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10210, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10217, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10235, add=0)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10238, add=0)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10242, add=0)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10244, add=0)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10248, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10250, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10254, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10259, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10263, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10267, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10271, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10275, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10279, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10284, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10288, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10292, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10296, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10300, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10304, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10308, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10312, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10316, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10345, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10352, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10359, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10377, add=0)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10380, add=0)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10384, add=0)
        cls.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10386, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10388, add=0)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10390, add=0)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10394, add=0)
        cls.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10396, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10398, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10400, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10404, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10409, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10413, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10417, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10421, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10425, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10429, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10434, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10438, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10442, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10446, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10450, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10454, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10458, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10462, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10466, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10506, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10513, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10520, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10560, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10567, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10574, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10615, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10622, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10629, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10670, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10677, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10684, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10726, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10733, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10740, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10782, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10789, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10796, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10838, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10845, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10852, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10894, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10901, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10908, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10950, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10957, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10964, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11017, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11024, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11031, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11073, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11080, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11087, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11129, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11136, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11143, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11184, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11191, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11198, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11240, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11247, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11254, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11296, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11303, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11310, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11351, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11358, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11365, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11382, add=0)
        self.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=11385, add=0)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11388, add=0)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11392, add=0)
        self.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11394, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11396, add=0)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11398, add=0)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11402, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11404, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11406, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11435, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11442, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11449, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11467, add=0)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11470, add=0)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11474, add=0)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11476, add=0)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11480, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11482, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11511, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11518, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11525, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11543, add=0)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11546, add=0)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11550, add=0)
        cls.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11552, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11554, add=0)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11556, add=0)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11560, add=0)
        cls.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11562, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11564, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11566, add=0)
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
update_stack(exp_stack=exp_stack0, line_num=11588, add=0)
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
update_stack(exp_stack=exp_stack0, line_num=11597, add=0)
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
update_stack(exp_stack=exp_stack0, line_num=11614, add=0)
func_get_caller_info_1(exp_stack=exp_stack0, capsys=None)

# call method
cls_get_caller_info01 = ClassGetCallerInfo1()
update_stack(exp_stack=exp_stack0, line_num=11619, add=0)
cls_get_caller_info01.get_caller_info_m1(exp_stack=exp_stack0, capsys=None)

# call static method
update_stack(exp_stack=exp_stack0, line_num=11623, add=0)
cls_get_caller_info01.get_caller_info_s1(exp_stack=exp_stack0, capsys=None)

# call class method
update_stack(exp_stack=exp_stack0, line_num=11627, add=0)
ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack0, capsys=None)

# call overloaded base class method
update_stack(exp_stack=exp_stack0, line_num=11631, add=0)
cls_get_caller_info01.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class static method
update_stack(exp_stack=exp_stack0, line_num=11635, add=0)
cls_get_caller_info01.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class class method
update_stack(exp_stack=exp_stack0, line_num=11639, add=0)
ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call subclass method
cls_get_caller_info01S = ClassGetCallerInfo1S()
update_stack(exp_stack=exp_stack0, line_num=11644, add=0)
cls_get_caller_info01S.get_caller_info_m1s(exp_stack=exp_stack0, capsys=None)

# call subclass static method
update_stack(exp_stack=exp_stack0, line_num=11648, add=0)
cls_get_caller_info01S.get_caller_info_s1s(exp_stack=exp_stack0, capsys=None)

# call subclass class method
update_stack(exp_stack=exp_stack0, line_num=11652, add=0)
ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass method
update_stack(exp_stack=exp_stack0, line_num=11656, add=0)
cls_get_caller_info01S.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass static method
update_stack(exp_stack=exp_stack0, line_num=11660, add=0)
cls_get_caller_info01S.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass class method
update_stack(exp_stack=exp_stack0, line_num=11664, add=0)
ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call base method from subclass method
update_stack(exp_stack=exp_stack0, line_num=11668, add=0)
cls_get_caller_info01S.get_caller_info_m1sb(exp_stack=exp_stack0, capsys=None)

# call base static method from subclass static method
update_stack(exp_stack=exp_stack0, line_num=11672, add=0)
cls_get_caller_info01S.get_caller_info_s1sb(exp_stack=exp_stack0, capsys=None)

# call base class method from subclass class method
update_stack(exp_stack=exp_stack0, line_num=11676, add=0)
ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack0, capsys=None)
