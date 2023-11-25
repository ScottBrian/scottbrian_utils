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
    # times are very close to 23:59:59 if the format does not include
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

    before_time = datetime.strptime(
        before_time.strftime(diag_msg_args.dt_format_arg), diag_msg_args.dt_format_arg
    )
    after_time = datetime.strptime(
        after_time.strftime(diag_msg_args.dt_format_arg), diag_msg_args.dt_format_arg
    )

    if diag_msg_args.file_arg == "sys.stdout":
        cap_msg = capsys.readouterr().out
    else:  # must be stderr
        cap_msg = capsys.readouterr().err

    str_list = cap_msg.split()
    dt_format_split_list = diag_msg_args.dt_format_arg.split()
    msg_time_str = ""
    for i in range(len(dt_format_split_list)):
        msg_time_str = f"{msg_time_str}{str_list.pop(0)} "
    msg_time_str = msg_time_str.rstrip()
    msg_time = datetime.strptime(msg_time_str, diag_msg_args.dt_format_arg)

    # if safe to proceed with low resolution
    if before_time <= after_time:
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
        update_stack(exp_stack=exp_stack, line_num=485, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=516, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=548, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=551, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=554, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=557, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=566, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=652, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=655, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=658, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=661, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=670, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=705, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=708, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=711, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=714, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=741, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=858, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=908, add=0)
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
            update_stack(exp_stack=exp_stack, line_num=911, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=914, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=917, add=0)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=920, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=923, add=0)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=926, add=0)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=929, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=936, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=939, add=2)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=944, add=0)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=947, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=954, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=959, add=4)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=966, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=973, add=5)
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

        update_stack(exp_stack=exp_stack, line_num=991, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=1023, add=0)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1026, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1029, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1032, add=0)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1035, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1038, add=0)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1041, add=0)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1044, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1051, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1054, add=2)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1059, add=0)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1062, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1069, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1074, add=4)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1081, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1088, add=5)
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

        update_stack(exp_stack=exp_stack, line_num=1106, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=1140, add=0)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1143, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1146, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1149, add=0)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1152, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1155, add=0)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1158, add=0)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1161, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1168, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1171, add=2)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1176, add=0)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1179, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1186, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1191, add=4)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1198, add=4)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1205, add=5)
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
    update_stack(exp_stack=exp_stack, line_num=1256, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=1263, add=0)
    call_seq = get_formatted_call_sequence(depth=1)

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    update_stack(exp_stack=exp_stack, line_num=1270, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=1284, add=0)
    func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info1 = ClassGetCallerInfo1()
    update_stack(exp_stack=exp_stack, line_num=1289, add=0)
    cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=1293, add=0)
    cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=1297, add=0)
    ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=1301, add=0)
    cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=1305, add=0)
    cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=1309, add=0)
    ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info1s = ClassGetCallerInfo1S()
    update_stack(exp_stack=exp_stack, line_num=1314, add=0)
    cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=1318, add=0)
    cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=1322, add=0)
    ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=1326, add=0)
    cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=1330, add=0)
    cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=1334, add=0)
    ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=1338, add=0)
    cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=1342, add=0)
    cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=1346, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1377, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1384, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1392, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1408, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1413, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1419, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1425, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1431, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1437, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1443, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1450, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1456, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1462, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1468, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1474, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1480, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1486, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1492, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1498, add=2)
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
            update_stack(exp_stack=exp_stack_g, line_num=1524, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1531, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1539, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1555, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1560, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1566, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1572, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1578, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1584, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1590, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1597, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1603, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1609, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1615, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1621, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1627, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1633, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1639, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1645, add=2)
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
            update_stack(exp_stack=exp_stack_g, line_num=1673, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1680, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1688, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1704, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1709, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1715, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1721, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1727, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1733, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1739, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1746, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1752, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1758, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1764, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1770, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1776, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1782, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1788, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1794, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=1827, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=1834, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=1842, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=1858, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=1863, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=1869, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=1875, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=1881, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=1887, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=1893, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=1900, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1906, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1912, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1918, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1924, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1930, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1936, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1942, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1948, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=1974, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=1981, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=1989, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2005, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=2010, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2016, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2022, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2028, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2034, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2040, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=2047, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2053, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2059, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2065, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2071, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2077, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2083, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2089, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2095, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=2123, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2130, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2138, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2154, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=2159, add=2)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2165, add=2)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2171, add=2)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2177, add=2)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2183, add=2)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2189, add=2)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=2196, add=2)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2202, add=2)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2208, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2214, add=2)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2220, add=2)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2226, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2232, add=2)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2238, add=2)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2244, add=2)
            ClassGetCallerInfo1S.get_caller_info_c1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

    a_inner = Inner()
    # call Inner method
    update_stack(exp_stack=exp_stack, line_num=2253, add=0)
    a_inner.g1(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2256, add=0)
    a_inner.g2_static(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2259, add=0)
    a_inner.g3_class(exp_stack_g=exp_stack, capsys_g=capsys)

    a_inherit = Inherit()

    update_stack(exp_stack=exp_stack, line_num=2264, add=0)
    a_inherit.h1(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2267, add=0)
    a_inherit.h2_static(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2270, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=2297, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=2304, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=2312, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=2328, add=0)
    func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info2 = ClassGetCallerInfo2()
    update_stack(exp_stack=exp_stack, line_num=2333, add=0)
    cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=2337, add=0)
    cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=2341, add=0)
    ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=2345, add=0)
    cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=2349, add=0)
    cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=2353, add=0)
    ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info2s = ClassGetCallerInfo2S()
    update_stack(exp_stack=exp_stack, line_num=2358, add=0)
    cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=2362, add=0)
    cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=2366, add=0)
    ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=2370, add=0)
    cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=2374, add=0)
    cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=2378, add=0)
    ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=2382, add=0)
    cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=2386, add=0)
    cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=2390, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2421, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2428, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2436, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2452, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2457, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2463, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2469, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2475, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2481, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2487, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2494, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2500, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2506, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2512, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2518, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2524, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2530, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2536, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2542, add=2)
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
            update_stack(exp_stack=exp_stack_g, line_num=2568, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2575, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2583, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2599, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2604, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2610, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2616, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2622, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2628, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2634, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2641, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2647, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2653, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2659, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2665, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2671, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2677, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2683, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2689, add=2)
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
            update_stack(exp_stack=exp_stack_g, line_num=2717, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2724, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2732, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2748, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2753, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2759, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2765, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2771, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2777, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2783, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2790, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2796, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2802, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2808, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2814, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2820, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2826, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2832, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2838, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=2871, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2878, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2886, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2902, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2907, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2913, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2919, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2925, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2931, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2937, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=2944, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2950, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2956, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2962, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2968, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2974, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2980, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2986, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2992, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=3018, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=3025, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=3033, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=3049, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=3054, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=3060, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=3066, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=3072, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=3078, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=3084, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=3091, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3097, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3103, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3109, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3115, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3121, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3127, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3133, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3139, add=2)
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
            update_stack(exp_stack=exp_stack_h, line_num=3167, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=3174, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=3182, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=3198, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=3203, add=2)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=3209, add=2)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=3215, add=2)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=3221, add=2)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=3227, add=2)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=3233, add=2)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=3240, add=2)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3246, add=2)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3252, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3258, add=2)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3264, add=2)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3270, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3276, add=2)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3282, add=2)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3288, add=2)
            ClassGetCallerInfo2S.get_caller_info_c2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

    a_inner = Inner()
    # call Inner method
    update_stack(exp_stack=exp_stack, line_num=3297, add=0)
    a_inner.g1(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=3300, add=0)
    a_inner.g2_static(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=3303, add=0)
    a_inner.g3_class(exp_stack_g=exp_stack, capsys_g=capsys)

    a_inherit = Inherit()

    update_stack(exp_stack=exp_stack, line_num=3308, add=0)
    a_inherit.h1(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=3311, add=0)
    a_inherit.h2_static(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=3314, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=3341, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=3348, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3356, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=3372, add=0)
    func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info3 = ClassGetCallerInfo3()
    update_stack(exp_stack=exp_stack, line_num=3377, add=0)
    cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=3381, add=0)
    cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=3385, add=0)
    ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=3389, add=0)
    cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=3393, add=0)
    cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=3397, add=0)
    ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info3s = ClassGetCallerInfo3S()
    update_stack(exp_stack=exp_stack, line_num=3402, add=0)
    cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=3406, add=0)
    cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=3410, add=0)
    ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=3414, add=0)
    cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=3418, add=0)
    cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=3422, add=0)
    ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=3426, add=0)
    cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=3430, add=0)
    cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=3434, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=3461, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=3468, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3476, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3524, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3531, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3538, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3554, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3559, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3563, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3567, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3571, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3575, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3579, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3584, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3588, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3592, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3596, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3600, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3604, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3608, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3612, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3616, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3639, add=0)
        self.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3641, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)

        update_stack(exp_stack=exp_stack, line_num=3644, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3646, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3670, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3677, add=0)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3684, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3700, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3705, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3709, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3713, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3717, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3721, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3725, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3730, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3734, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3738, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3742, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3746, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3750, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3754, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3758, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3762, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3788, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3795, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3802, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3818, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3823, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3827, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3831, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3835, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3839, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3843, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3848, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3852, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3856, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3860, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3864, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3868, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3872, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3876, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3880, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3906, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3913, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3920, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3936, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3941, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3945, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3949, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3953, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3957, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3961, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3966, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3970, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3974, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3978, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3982, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3986, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3990, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3994, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3998, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4025, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4032, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4039, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4055, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4060, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4064, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4068, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4072, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4076, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4080, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4085, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4089, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4093, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4097, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4101, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4105, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4109, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4113, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4117, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4144, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4151, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4158, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4174, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4179, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4183, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4187, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4191, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4195, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4199, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4204, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4208, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4212, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4216, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4220, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4224, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4228, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4232, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4236, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4262, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4269, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4276, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4292, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4297, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4301, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4305, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4309, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4313, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4317, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4322, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4326, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4330, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4334, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4338, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4342, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4346, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4350, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4354, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4383, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4390, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4397, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4413, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4418, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4422, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4426, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4430, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4434, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4438, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4443, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4447, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4451, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4455, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4459, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4463, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4467, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4471, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4475, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4502, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4509, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4516, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4532, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4537, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4541, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4545, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4549, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4553, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4557, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4562, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4566, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4570, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4574, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4578, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4582, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4586, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4590, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4594, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4625, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4632, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4639, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4655, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4660, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4664, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4668, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4672, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4676, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4680, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4685, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4689, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4693, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4697, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4701, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4705, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4709, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4713, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4717, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4749, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4756, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4763, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4779, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4784, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4788, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4792, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4796, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4800, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4804, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4809, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4813, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4817, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4821, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4825, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4829, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4833, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4837, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4841, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4868, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4875, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4882, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4898, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4903, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4907, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4911, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4915, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4919, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4923, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4928, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4932, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4936, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4940, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4944, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4948, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4952, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4956, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4960, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4987, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4994, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5001, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5017, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5022, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5026, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5030, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5034, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5038, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5042, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5047, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5051, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5055, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5059, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5063, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5067, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5071, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5075, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5079, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5105, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5112, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5119, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5135, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5140, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5144, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5148, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5152, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5156, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5160, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5165, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5169, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5173, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5177, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5181, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5185, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5189, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5193, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5197, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5224, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5231, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5238, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5254, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5259, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5263, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5267, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5271, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5275, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5279, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5284, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5288, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5292, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5296, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5300, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5304, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5308, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5312, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5316, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5343, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5350, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5357, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5373, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5378, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5382, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5386, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5390, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5394, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5398, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5403, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5407, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5411, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5415, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5419, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5423, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5427, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5431, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5435, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5461, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5468, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5475, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5491, add=0)
        self.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        update_stack(exp_stack=exp_stack, line_num=5494, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5497, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5501, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5503, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5505, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5507, add=2)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5513, add=0)
        super().get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5515, add=0)
        TestClassGetCallerInfo0.get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5517, add=2)
        TestClassGetCallerInfo0S.get_caller_info_c0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5523, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5528, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5532, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5536, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5540, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5544, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5548, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5553, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5557, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5561, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5565, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5569, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5573, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5577, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5581, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5585, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5612, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5619, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5626, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5643, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5646, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5650, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5652, add=2)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5658, add=0)
        TestClassGetCallerInfo0.get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5660, add=2)
        TestClassGetCallerInfo0S.get_caller_info_c0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5666, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5671, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5675, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5679, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5683, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5687, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5691, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5696, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5700, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5704, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5708, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5712, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5716, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5720, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5724, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5728, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5755, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5762, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5769, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5786, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5789, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5793, add=0)
        cls.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5795, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5797, add=0)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5799, add=2)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )
        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5804, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5809, add=0)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5813, add=0)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5817, add=0)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5821, add=0)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5825, add=0)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5829, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5834, add=0)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5838, add=0)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5842, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5846, add=0)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5850, add=0)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5854, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5858, add=0)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5862, add=0)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5866, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5906, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5913, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=5920, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5937, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=5942, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5946, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5950, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5954, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5958, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5962, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=5967, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5971, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5975, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5979, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5983, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5987, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5991, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5995, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5999, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6026, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6033, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6040, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6057, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6062, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6066, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6070, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6074, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6078, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6082, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6087, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6091, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6095, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6099, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6103, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6107, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6111, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6115, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6119, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6147, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6154, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6161, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6178, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6183, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6187, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6191, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6195, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6199, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6203, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6208, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6212, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6216, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6220, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6224, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6228, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6232, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6236, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6240, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6268, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6275, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6282, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6299, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6304, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6308, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6312, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6316, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6320, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6324, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6329, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6333, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6337, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6341, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6345, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6349, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6353, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6357, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6361, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6390, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6397, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6404, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6421, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6426, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6430, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6434, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6438, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6442, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6446, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6451, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6455, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6459, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6463, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6467, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6471, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6475, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6479, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6483, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6512, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6519, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6526, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6543, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6548, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6552, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6556, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6560, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6564, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6568, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6573, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6577, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6581, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6585, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6589, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6593, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6597, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6601, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6605, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6634, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6641, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6648, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6665, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6670, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6674, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6678, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6682, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6686, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6690, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6695, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6699, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6703, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6707, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6711, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6715, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6719, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6723, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6727, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6756, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6763, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6770, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6787, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6792, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6796, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6800, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6804, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6808, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6812, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6817, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6821, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6825, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6829, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6833, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6837, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6841, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6845, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6849, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6878, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6885, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6892, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6909, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6914, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6918, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6922, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6926, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6930, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6934, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6939, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6943, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6947, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6951, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6955, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6959, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6963, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6967, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6971, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7011, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7018, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7025, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7042, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7047, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7051, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7055, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7059, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7063, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7067, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7072, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7076, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7080, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7084, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7088, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7092, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7096, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7100, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7104, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7133, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7140, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7147, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7164, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7169, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7173, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7177, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7181, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7185, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7189, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7194, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7198, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7202, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7206, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7210, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7214, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7218, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7222, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7226, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7255, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7262, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7269, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7286, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7291, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7295, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7299, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7303, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7307, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7311, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7316, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7320, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7324, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7328, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7332, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7336, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7340, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7344, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7348, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7376, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7383, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7390, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7407, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7412, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7416, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7420, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7424, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7428, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7432, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7437, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7441, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7445, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7449, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7453, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7457, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7461, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7465, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7469, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7498, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7505, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7512, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7529, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7534, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7538, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7542, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7546, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7550, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7554, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7559, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7563, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7567, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7571, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7575, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7579, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7583, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7587, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7591, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7620, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7627, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7634, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7651, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7656, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7660, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7664, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7668, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7672, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7676, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7681, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7685, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7689, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7693, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7697, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7701, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7705, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7709, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7713, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7741, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7748, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7755, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7772, add=0)
        self.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=7775, add=0)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7778, add=0)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7782, add=0)
        self.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7784, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7786, add=0)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7788, add=0)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7792, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7794, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7796, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7800, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7805, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7809, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7813, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7817, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7821, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7825, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7830, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7834, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7838, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7842, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7846, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7850, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7854, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7858, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7862, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7891, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7898, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7905, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7923, add=0)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7926, add=0)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7930, add=0)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7932, add=0)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7936, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7938, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7942, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7947, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7951, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7955, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7959, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7963, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7967, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7972, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7976, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7980, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7984, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7988, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7992, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7996, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8000, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8004, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8033, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8040, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8047, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8065, add=0)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=8068, add=0)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=8072, add=0)
        cls.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8074, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8076, add=0)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8078, add=0)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=8082, add=0)
        cls.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8084, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8086, add=0)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8088, add=0)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8092, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=8097, add=0)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8101, add=0)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8105, add=0)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8109, add=0)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8113, add=0)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8117, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=8122, add=0)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8126, add=0)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8130, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8134, add=0)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8138, add=0)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8142, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8146, add=0)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8150, add=0)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8154, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8194, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8201, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8208, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8225, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8230, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8234, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8238, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8242, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8246, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8250, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8255, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8259, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8263, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8267, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8271, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8275, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8279, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8283, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8287, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8314, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8321, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8328, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8345, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8350, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8354, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8358, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8362, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8366, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8370, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8375, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8379, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8383, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8387, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8391, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8395, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8399, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8403, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8407, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8435, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8442, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8449, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8466, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8471, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8475, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8479, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8483, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8487, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8491, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8496, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8500, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8504, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8508, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8512, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8516, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8520, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8524, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8528, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8556, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8563, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8570, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8587, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8592, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8596, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8600, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8604, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8608, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8612, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8617, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8621, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8625, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8629, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8633, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8637, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8641, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8645, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8649, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8678, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8685, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8692, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8709, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8714, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8718, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8722, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8726, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8730, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8734, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8739, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8743, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8747, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8751, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8755, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8759, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8763, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8767, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8771, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8800, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8807, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8814, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8831, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8836, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8840, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8844, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8848, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8852, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8856, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8861, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8865, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8869, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8873, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8877, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8881, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8885, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8889, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8893, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8922, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8929, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8936, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8953, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8958, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8962, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8966, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8970, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8974, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8978, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8983, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8987, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8991, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8995, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8999, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9003, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9007, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9011, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9015, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9044, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9051, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9058, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9075, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9080, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9084, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9088, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9092, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9096, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9100, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9105, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9109, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9113, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9117, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9121, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9125, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9129, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9133, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9137, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9166, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9173, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9180, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9197, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9202, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9206, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9210, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9214, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9218, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9222, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9227, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9231, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9235, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9239, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9243, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9247, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9251, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9255, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9259, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9299, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9306, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9313, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9330, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9335, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9339, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9343, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9347, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9351, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9355, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9360, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9364, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9368, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9372, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9376, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9380, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9384, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9388, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9392, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9421, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9428, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9435, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9452, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9457, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9461, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9465, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9469, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9473, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9477, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9482, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9486, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9490, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9494, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9498, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9502, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9506, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9510, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9514, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9543, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9550, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9557, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9574, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9579, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9583, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9587, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9591, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9595, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9599, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9604, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9608, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9612, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9616, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9620, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9624, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9628, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9632, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9636, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9664, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9671, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9678, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9695, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9700, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9704, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9708, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9712, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9716, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9720, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9725, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9729, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9733, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9737, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9741, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9745, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9749, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9753, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9757, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9786, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9793, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9800, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9817, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9822, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9826, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9830, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9834, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9838, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9842, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9847, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9851, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9855, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9859, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9863, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9867, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9871, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9875, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9879, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9908, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9915, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9922, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9939, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9944, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9948, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9952, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9956, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9960, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9964, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9969, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9973, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9977, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9981, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9985, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9989, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9993, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9997, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10001, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10029, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10036, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10043, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10060, add=0)
        self.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=10063, add=0)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10066, add=0)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10070, add=0)
        self.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10072, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10074, add=0)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10076, add=0)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10080, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10082, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10084, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10088, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10093, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10097, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10101, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10105, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10109, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10113, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10118, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10122, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10126, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10130, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10134, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10138, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10142, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10146, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10150, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10179, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10186, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10193, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10211, add=0)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10214, add=0)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10218, add=0)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10220, add=0)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10224, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10226, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10230, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10235, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10239, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10243, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10247, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10251, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10255, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10260, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10264, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10268, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10272, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10276, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10280, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10284, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10288, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10292, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10321, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10328, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10335, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10353, add=0)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10356, add=0)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10360, add=0)
        cls.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10362, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10364, add=0)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10366, add=0)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10370, add=0)
        cls.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10372, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10374, add=0)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10376, add=0)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10380, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10385, add=0)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10389, add=0)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10393, add=0)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10397, add=0)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10401, add=0)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10405, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10410, add=0)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10414, add=0)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10418, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10422, add=0)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10426, add=0)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10430, add=0)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10434, add=0)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10438, add=0)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10442, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10482, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10489, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10496, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10536, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10543, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10550, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10591, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10598, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10605, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10646, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10653, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10660, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10702, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10709, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10716, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10758, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10765, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10772, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10814, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10821, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10828, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10870, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10877, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10884, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10926, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10933, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10940, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10993, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11000, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11007, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11049, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11056, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11063, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11105, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11112, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11119, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11160, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11167, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11174, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11216, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11223, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11230, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11272, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11279, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11286, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11327, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11334, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11341, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11358, add=0)
        self.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=11361, add=0)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11364, add=0)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11368, add=0)
        self.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11370, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11372, add=0)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11374, add=0)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11378, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11380, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11382, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11411, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11418, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11425, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11443, add=0)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11446, add=0)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11450, add=0)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11452, add=0)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11456, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11458, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11487, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11494, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11501, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11519, add=0)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11522, add=0)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11526, add=0)
        cls.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11528, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11530, add=0)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11532, add=0)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11536, add=0)
        cls.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11538, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11540, add=0)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11542, add=0)
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
update_stack(exp_stack=exp_stack0, line_num=11564, add=0)
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
update_stack(exp_stack=exp_stack0, line_num=11573, add=0)
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
update_stack(exp_stack=exp_stack0, line_num=11590, add=0)
func_get_caller_info_1(exp_stack=exp_stack0, capsys=None)

# call method
cls_get_caller_info01 = ClassGetCallerInfo1()
update_stack(exp_stack=exp_stack0, line_num=11595, add=0)
cls_get_caller_info01.get_caller_info_m1(exp_stack=exp_stack0, capsys=None)

# call static method
update_stack(exp_stack=exp_stack0, line_num=11599, add=0)
cls_get_caller_info01.get_caller_info_s1(exp_stack=exp_stack0, capsys=None)

# call class method
update_stack(exp_stack=exp_stack0, line_num=11603, add=0)
ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack0, capsys=None)

# call overloaded base class method
update_stack(exp_stack=exp_stack0, line_num=11607, add=0)
cls_get_caller_info01.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class static method
update_stack(exp_stack=exp_stack0, line_num=11611, add=0)
cls_get_caller_info01.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class class method
update_stack(exp_stack=exp_stack0, line_num=11615, add=0)
ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call subclass method
cls_get_caller_info01S = ClassGetCallerInfo1S()
update_stack(exp_stack=exp_stack0, line_num=11620, add=0)
cls_get_caller_info01S.get_caller_info_m1s(exp_stack=exp_stack0, capsys=None)

# call subclass static method
update_stack(exp_stack=exp_stack0, line_num=11624, add=0)
cls_get_caller_info01S.get_caller_info_s1s(exp_stack=exp_stack0, capsys=None)

# call subclass class method
update_stack(exp_stack=exp_stack0, line_num=11628, add=0)
ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass method
update_stack(exp_stack=exp_stack0, line_num=11632, add=0)
cls_get_caller_info01S.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass static method
update_stack(exp_stack=exp_stack0, line_num=11636, add=0)
cls_get_caller_info01S.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass class method
update_stack(exp_stack=exp_stack0, line_num=11640, add=0)
ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call base method from subclass method
update_stack(exp_stack=exp_stack0, line_num=11644, add=0)
cls_get_caller_info01S.get_caller_info_m1sb(exp_stack=exp_stack0, capsys=None)

# call base static method from subclass static method
update_stack(exp_stack=exp_stack0, line_num=11648, add=0)
cls_get_caller_info01S.get_caller_info_s1sb(exp_stack=exp_stack0, capsys=None)

# call base class method from subclass class method
update_stack(exp_stack=exp_stack0, line_num=11652, add=0)
ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack0, capsys=None)
