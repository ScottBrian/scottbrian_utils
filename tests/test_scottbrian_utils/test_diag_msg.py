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
        update_stack(exp_stack=exp_stack, line_num=480, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=509, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=540, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=543, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=546, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=549, add=1)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=557, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=587, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=590, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=593, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=596, add=1)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=604, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=636, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=639, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=642, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=645, add=1)
            call_seq = get_formatted_call_sequence(latest=latest_arg, depth=depth_arg)
        verify_call_seq(
            exp_stack=exp_stack,
            call_seq=call_seq,
            seq_latest=latest_arg,
            seq_depth=depth_arg,
        )

        update_stack(exp_stack=exp_stack, line_num=653, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=685, add=0)
        call_seq = ""
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=688, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=691, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=694, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=718, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=829, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=871, add=0)
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
            update_stack(exp_stack=exp_stack, line_num=874, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=877, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=880, add=1)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=884, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=887, add=1)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=891, add=1)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=895, add=2)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=900, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=903, add=1)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=907, add=1)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=911, add=2)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=916, add=1)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=920, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=925, add=2)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=930, add=3)
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

        update_stack(exp_stack=exp_stack, line_num=944, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=972, add=0)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=975, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=978, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=981, add=1)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=985, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=988, add=1)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=992, add=1)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=996, add=2)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1001, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1004, add=1)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1008, add=1)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1012, add=2)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1017, add=1)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1021, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1026, add=2)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1031, add=3)
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

        update_stack(exp_stack=exp_stack, line_num=1045, add=2)
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
        update_stack(exp_stack=exp_stack, line_num=1075, add=0)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1078, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1081, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1084, add=1)
            diag_msg(*diag_msg_args.msg_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1088, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1091, add=1)
            diag_msg(depth=diag_msg_args.depth_arg, file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1095, add=1)
            diag_msg(*diag_msg_args.msg_arg, depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1099, add=2)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1104, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1107, add=1)
            diag_msg(
                dt_format=diag_msg_args.dt_format_arg, file=eval(diag_msg_args.file_arg)
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1111, add=1)
            diag_msg(*diag_msg_args.msg_arg, dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1115, add=2)
            diag_msg(
                *diag_msg_args.msg_arg,
                dt_format=diag_msg_args.dt_format_arg,
                file=eval(diag_msg_args.file_arg),
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1120, add=1)
            diag_msg(
                depth=diag_msg_args.depth_arg, dt_format=diag_msg_args.dt_format_arg
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1124, add=2)
            diag_msg(
                depth=diag_msg_args.depth_arg,
                file=eval(diag_msg_args.file_arg),
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1129, add=2)
            diag_msg(
                *diag_msg_args.msg_arg,
                depth=diag_msg_args.depth_arg,
                dt_format=diag_msg_args.dt_format_arg,
            )
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1134, add=3)
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
    update_stack(exp_stack=exp_stack, line_num=1179, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=1186, add=0)
    call_seq = get_formatted_call_sequence(depth=1)

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    update_stack(exp_stack=exp_stack, line_num=1193, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=1206, add=0)
    func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info1 = ClassGetCallerInfo1()
    update_stack(exp_stack=exp_stack, line_num=1211, add=0)
    cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=1215, add=0)
    cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=1219, add=0)
    ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=1223, add=1)
    cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=1228, add=1)
    cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=1233, add=1)
    ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info1s = ClassGetCallerInfo1S()
    update_stack(exp_stack=exp_stack, line_num=1239, add=1)
    cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=1244, add=1)
    cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=1249, add=1)
    ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=1254, add=1)
    cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=1259, add=1)
    cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=1264, add=1)
    ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=1269, add=1)
    cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=1274, add=1)
    cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=1279, add=1)
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
            update_stack(exp_stack=exp_stack_g, line_num=1312, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1319, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1327, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1341, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1346, add=1)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1351, add=1)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1356, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1361, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1366, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1371, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1377, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1382, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1387, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1392, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1397, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1402, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1407, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1412, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1417, add=1)
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
            update_stack(exp_stack=exp_stack_g, line_num=1442, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1449, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1457, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1471, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1476, add=1)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1481, add=1)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1486, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1491, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1496, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1501, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1507, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1512, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1517, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1522, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1527, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1532, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1537, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1542, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1547, add=1)
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
            update_stack(exp_stack=exp_stack_g, line_num=1573, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1580, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1588, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1602, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1607, add=1)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1612, add=1)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1617, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1622, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1627, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1632, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1638, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1643, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1648, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1653, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1658, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1663, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1668, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1673, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1678, add=1)
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
            update_stack(exp_stack=exp_stack_h, line_num=1711, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=1718, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=1726, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=1740, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=1745, add=1)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=1750, add=1)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=1755, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=1760, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=1765, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=1770, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=1776, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1781, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1786, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1791, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1796, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1801, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1806, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1811, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1816, add=1)
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
            update_stack(exp_stack=exp_stack_h, line_num=1841, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=1848, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=1856, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=1870, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=1875, add=1)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=1880, add=1)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=1885, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=1890, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=1895, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=1900, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=1906, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1911, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1916, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1921, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1926, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1931, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1936, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1941, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1946, add=1)
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
            update_stack(exp_stack=exp_stack_h, line_num=1972, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=1979, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=1987, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2001, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=2006, add=1)
            cls_get_caller_info1.get_caller_info_m1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2011, add=1)
            cls_get_caller_info1.get_caller_info_s1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2016, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2021, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2026, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2031, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=2037, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2042, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2047, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2052, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2057, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2062, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2067, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2072, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2077, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

    a_inner = Inner()
    # call Inner method
    update_stack(exp_stack=exp_stack, line_num=2085, add=0)
    a_inner.g1(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2088, add=0)
    a_inner.g2_static(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2091, add=0)
    a_inner.g3_class(exp_stack_g=exp_stack, capsys_g=capsys)

    a_inherit = Inherit()

    update_stack(exp_stack=exp_stack, line_num=2096, add=0)
    a_inherit.h1(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2099, add=0)
    a_inherit.h2_static(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2102, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=2128, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=2135, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=2143, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=2156, add=0)
    func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info2 = ClassGetCallerInfo2()
    update_stack(exp_stack=exp_stack, line_num=2161, add=0)
    cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=2165, add=0)
    cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=2169, add=0)
    ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=2173, add=1)
    cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=2178, add=1)
    cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=2183, add=1)
    ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info2s = ClassGetCallerInfo2S()
    update_stack(exp_stack=exp_stack, line_num=2189, add=1)
    cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=2194, add=1)
    cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=2199, add=1)
    ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=2204, add=1)
    cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=2209, add=1)
    cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=2214, add=1)
    ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=2219, add=1)
    cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=2224, add=1)
    cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=2229, add=1)
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
            update_stack(exp_stack=exp_stack_g, line_num=2261, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2268, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2276, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2290, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2295, add=1)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2300, add=1)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2305, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2310, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2315, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2320, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2326, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2331, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2336, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2341, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2346, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2351, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2356, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2361, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2366, add=1)
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
            update_stack(exp_stack=exp_stack_g, line_num=2391, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2398, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2406, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2420, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2425, add=1)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2430, add=1)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2435, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2440, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2445, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2450, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2456, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2461, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2466, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2471, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2476, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2481, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2486, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2491, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2496, add=1)
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
            update_stack(exp_stack=exp_stack_g, line_num=2522, add=0)
            for i_g, expected_caller_info_g in enumerate(list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2529, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2537, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2551, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2556, add=1)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2561, add=1)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2566, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2571, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2576, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2581, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2587, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2592, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2597, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2602, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2607, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2612, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2617, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2622, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_g, capsys=capsys_g
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2627, add=1)
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
            update_stack(exp_stack=exp_stack_h, line_num=2659, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2666, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2674, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2688, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2693, add=1)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2698, add=1)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2703, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2708, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2713, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2718, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=2724, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2729, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2734, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2739, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2744, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2749, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2754, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2759, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2764, add=1)
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
            update_stack(exp_stack=exp_stack_h, line_num=2789, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2796, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2804, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2818, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2823, add=1)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2828, add=1)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2833, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2838, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2843, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2848, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=2854, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2859, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2864, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2869, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2874, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2879, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2884, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2889, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2894, add=1)
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
            update_stack(exp_stack=exp_stack_h, line_num=2920, add=0)
            for i_h, expected_caller_info_h in enumerate(list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2927, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2935, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2949, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2954, add=1)
            cls_get_caller_info2.get_caller_info_m2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2959, add=1)
            cls_get_caller_info2.get_caller_info_s2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2964, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2969, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2974, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2979, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=2985, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2990, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2995, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3000, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3005, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3010, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3015, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3020, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3025, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2sb(
                exp_stack=exp_stack_h, capsys=capsys_h
            )

            exp_stack.pop()

    a_inner = Inner()
    # call Inner method
    update_stack(exp_stack=exp_stack, line_num=3033, add=0)
    a_inner.g1(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=3036, add=0)
    a_inner.g2_static(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=3039, add=0)
    a_inner.g3_class(exp_stack_g=exp_stack, capsys_g=capsys)

    a_inherit = Inherit()

    update_stack(exp_stack=exp_stack, line_num=3044, add=0)
    a_inherit.h1(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=3047, add=0)
    a_inherit.h2_static(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=3050, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=3076, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=3083, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3091, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=3104, add=0)
    func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info3 = ClassGetCallerInfo3()
    update_stack(exp_stack=exp_stack, line_num=3109, add=0)
    cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=3113, add=0)
    cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=3117, add=0)
    ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=3121, add=1)
    cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=3126, add=1)
    cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=3131, add=1)
    ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

    # call subclass method
    cls_get_caller_info3s = ClassGetCallerInfo3S()
    update_stack(exp_stack=exp_stack, line_num=3137, add=1)
    cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=3142, add=1)
    cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=3147, add=1)
    ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=3152, add=1)
    cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=3157, add=1)
    cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=3162, add=1)
    ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=3167, add=1)
    cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=3172, add=1)
    cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=3177, add=1)
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
    update_stack(exp_stack=exp_stack, line_num=3204, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=3211, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3219, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3263, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3270, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3277, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3290, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3295, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3300, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3305, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3310, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3315, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3320, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3326, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3331, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3336, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3341, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3346, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3351, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3356, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3361, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3366, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=3390, add=0)
        self.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3392, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)

        update_stack(exp_stack=exp_stack, line_num=3396, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3398, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=3420, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3427, add=0)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3434, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3447, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3452, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3457, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3462, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3467, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3472, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3477, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3483, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3488, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3493, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3498, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3503, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3508, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3513, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3518, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3523, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=3549, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3556, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3563, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3576, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3581, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3586, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3591, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3596, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3601, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3606, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3612, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3617, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3622, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3627, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3632, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3637, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3642, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3647, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3652, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=3678, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3685, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3692, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3705, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3710, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3715, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3720, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3725, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3730, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3735, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3741, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3746, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3751, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3756, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3761, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3766, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3771, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3776, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3781, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=3807, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3814, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3821, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3834, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3839, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3844, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3849, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3854, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3859, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3864, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3870, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3875, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3880, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3885, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3890, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3895, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3900, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3905, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3910, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=3937, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3944, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3951, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3964, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3969, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3974, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3979, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3984, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3989, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3994, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4000, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4005, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4010, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4015, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4020, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4025, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4030, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4035, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4040, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=4066, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4073, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4080, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4093, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4098, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4103, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4108, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4113, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4118, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4123, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4129, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4134, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4139, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4144, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4149, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4154, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4159, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4164, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4169, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=4196, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4203, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4210, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4223, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4228, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4233, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4238, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4243, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4248, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4253, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4259, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4264, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4269, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4274, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4279, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4284, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4289, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4294, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4299, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=4327, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4334, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4341, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4354, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4359, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4364, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4369, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4374, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4379, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4384, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4390, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4395, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4400, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4405, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4410, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4415, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4420, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4425, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4430, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=4461, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4468, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4475, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4488, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4493, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4498, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4503, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4508, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4513, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4518, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4524, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4529, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4534, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4539, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4544, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4549, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4554, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4559, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4564, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=4596, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4603, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4610, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4623, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4628, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4633, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4638, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4643, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4648, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4653, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4659, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4664, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4669, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4674, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4679, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4684, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4689, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4694, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4699, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=4725, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4732, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4739, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4752, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4757, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4762, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4767, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4772, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4777, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4782, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4788, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4793, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4798, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4803, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4808, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4813, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4818, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4823, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4828, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=4855, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4862, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4869, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4882, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4887, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4892, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4897, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4902, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4907, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4912, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4918, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4923, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4928, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4933, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4938, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4943, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4948, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4953, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4958, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=4984, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4991, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4998, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5011, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5016, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5021, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5026, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5031, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5036, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5041, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5047, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5052, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5057, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5062, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5067, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5072, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5077, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5082, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5087, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=5113, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5120, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5127, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5140, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5145, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5150, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5155, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5160, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5165, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5170, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5176, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5181, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5186, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5191, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5196, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5201, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5206, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5211, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5216, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=5243, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5250, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5257, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5270, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5275, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5280, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5285, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5290, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5295, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5300, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5306, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5311, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5316, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5321, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5326, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5331, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5336, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5341, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5346, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=5372, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5379, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5386, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5399, add=0)
        self.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        update_stack(exp_stack=exp_stack, line_num=5402, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5405, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5409, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5411, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5413, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5416, add=1)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5421, add=0)
        super().get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5423, add=1)
        TestClassGetCallerInfo0.get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5426, add=1)
        TestClassGetCallerInfo0S.get_caller_info_c0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5431, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5436, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5441, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5446, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5451, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5456, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5461, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5467, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5472, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5477, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5482, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5487, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5492, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5497, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5502, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5507, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=5533, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5540, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5547, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5561, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5564, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5568, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5571, add=1)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5576, add=1)
        TestClassGetCallerInfo0.get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5579, add=1)
        TestClassGetCallerInfo0S.get_caller_info_c0bt(
            exp_stack=exp_stack, capsys=capsys
        )

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5584, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5589, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5594, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5599, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5604, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5609, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5614, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5620, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5625, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5630, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5635, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5640, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5645, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5650, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5655, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5660, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=5687, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5694, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5701, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5715, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5718, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5722, add=1)
        cls.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5725, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5727, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5730, add=1)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(
            exp_stack=exp_stack, capsys=capsys
        )
        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5734, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5739, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5744, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5749, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5754, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5759, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5764, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5770, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5775, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5780, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5785, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5790, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5795, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5800, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5805, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5810, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=5849, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5856, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=5863, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5878, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=5883, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5888, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5893, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5898, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5903, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5908, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=5914, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5919, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5924, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5929, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5934, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5939, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5944, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5949, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5954, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=5981, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5988, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=5995, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6010, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6015, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6020, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6025, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6030, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6035, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6040, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6046, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6051, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6056, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6061, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6066, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6071, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6076, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6081, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6086, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=6113, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6120, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6127, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6142, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6147, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6152, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6157, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6162, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6167, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6172, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6178, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6183, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6188, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6193, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6198, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6203, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6208, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6213, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6218, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=6245, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6252, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6259, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6274, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6279, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6284, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6289, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6294, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6299, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6304, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6310, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6315, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6320, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6325, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6330, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6335, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6340, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6345, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6350, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=6377, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6384, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6391, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6406, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6411, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6416, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6421, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6426, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6431, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6436, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6442, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6447, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6452, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6457, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6462, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6467, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6472, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6477, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6482, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=6510, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6517, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6524, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6539, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6544, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6549, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6554, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6559, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6564, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6569, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6575, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6580, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6585, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6590, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6595, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6600, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6605, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6610, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6615, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=6643, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6650, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6657, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6672, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6677, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6682, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6687, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6692, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6697, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6702, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6708, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6713, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6718, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6723, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6728, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6733, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6738, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6743, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6748, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=6775, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6782, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6789, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6804, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6809, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6814, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6819, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6824, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6829, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6834, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6840, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6845, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6850, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6855, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6860, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6865, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6870, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6875, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6880, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=6908, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6915, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6922, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6937, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6942, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6947, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6952, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6957, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6962, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6967, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6973, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6978, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6983, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6988, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6993, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6998, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7003, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7008, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7013, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=7052, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7059, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7066, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7081, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7086, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7091, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7096, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7101, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7106, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7111, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7117, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7122, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7127, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7132, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7137, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7142, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7147, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7152, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7157, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=7184, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7191, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7198, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7213, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7218, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7223, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7228, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7233, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7238, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7243, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7249, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7254, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7259, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7264, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7269, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7274, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7279, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7284, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7289, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=7317, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7324, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7331, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7346, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7351, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7356, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7361, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7366, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7371, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7376, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7382, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7387, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7392, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7397, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7402, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7407, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7412, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7417, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7422, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=7449, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7456, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7463, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7478, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7483, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7488, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7493, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7498, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7503, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7508, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7514, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7519, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7524, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7529, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7534, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7539, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7544, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7549, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7554, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=7581, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7588, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7595, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7610, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7615, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7620, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7625, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7630, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7635, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7640, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7646, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7651, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7656, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7661, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7666, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7671, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7676, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7681, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7686, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=7714, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7721, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7728, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7743, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7748, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7753, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7758, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7763, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7768, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7773, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7779, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7784, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7789, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7794, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7799, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7804, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7809, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7814, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7819, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=7846, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7853, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7860, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7875, add=0)
        self.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=7878, add=1)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7882, add=1)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7887, add=0)
        self.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7889, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7891, add=1)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7894, add=1)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7899, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7901, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7904, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7909, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7914, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7919, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7924, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7929, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7934, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7939, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7945, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7950, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7955, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7960, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7965, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7970, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7975, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7980, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7985, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=8012, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8019, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8026, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8042, add=1)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=8046, add=1)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=8051, add=1)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8054, add=1)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=8059, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8062, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8067, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=8072, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8077, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8082, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8087, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8092, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8097, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=8103, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8108, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8113, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8118, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8123, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8128, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8133, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8138, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8143, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=8171, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8178, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8185, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8201, add=1)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=8205, add=1)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=8210, add=1)
        cls.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8213, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8215, add=1)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8218, add=1)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=8223, add=0)
        cls.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8225, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8227, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8230, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8235, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=8240, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8245, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8250, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8255, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8260, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8265, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=8271, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8276, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8281, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8286, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8291, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8296, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8301, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8306, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8311, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=8350, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8357, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8364, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8379, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8384, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8389, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8394, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8399, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8404, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8409, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8415, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8420, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8425, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8430, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8435, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8440, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8445, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8450, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8455, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=8482, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8489, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8496, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8511, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8516, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8521, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8526, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8531, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8536, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8541, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8547, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8552, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8557, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8562, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8567, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8572, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8577, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8582, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8587, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=8643, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8648, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8653, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8658, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8663, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8668, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8673, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8679, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8684, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8689, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8694, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8699, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8704, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8709, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8714, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8719, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=8746, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8753, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8760, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8775, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8780, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8785, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8790, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8795, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8800, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8805, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8811, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8816, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8821, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8826, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8831, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8836, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8841, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8846, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8851, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=8878, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8885, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8892, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8907, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8912, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8917, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8922, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8927, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8932, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8937, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8943, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8948, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8953, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8958, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8963, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8968, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8973, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8978, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8983, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=9011, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9018, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9025, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9040, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9045, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9050, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9055, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9060, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9065, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9070, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9076, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9081, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9086, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9091, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9096, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9101, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9106, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9111, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9116, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=9144, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9151, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9158, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9173, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9178, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9183, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9188, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9193, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9198, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9203, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9209, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9214, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9219, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9224, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9229, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9234, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9239, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9244, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9249, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=9276, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9283, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9290, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9305, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9310, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9315, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9320, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9325, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9330, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9335, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9341, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9346, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9351, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9356, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9361, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9366, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9371, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9376, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9381, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=9409, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9416, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9423, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9438, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9443, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9448, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9453, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9458, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9463, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9468, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9474, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9479, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9484, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9489, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9494, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9499, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9504, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9509, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9514, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=9553, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9560, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9567, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9582, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9587, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9592, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9597, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9602, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9607, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9612, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9618, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9623, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9628, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9633, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9638, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9643, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9648, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9653, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9658, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=9685, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9692, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9699, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9714, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9719, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9724, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9729, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9734, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9739, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9744, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9750, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9755, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9760, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9765, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9770, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9775, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9780, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9785, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9790, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=9818, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9825, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9832, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9847, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9852, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9857, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9862, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9867, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9872, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9877, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9883, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9888, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9893, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9898, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9903, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9908, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9913, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9918, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9923, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=9950, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9957, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9964, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9979, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9984, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9989, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9994, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9999, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10004, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10009, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10015, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10020, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10025, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10030, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10035, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10040, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10045, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10050, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10055, add=1)
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

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10111, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10116, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10121, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10126, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10131, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10136, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10141, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10147, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10152, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10157, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10162, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10167, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10172, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10177, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10182, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10187, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=10215, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10222, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10229, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10244, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10249, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10254, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10259, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10264, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10269, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10274, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10280, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10285, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10290, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10295, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10300, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10305, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10310, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10315, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10320, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=10347, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10354, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10361, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10376, add=0)
        self.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=10379, add=1)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10383, add=1)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10388, add=0)
        self.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10390, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10392, add=1)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10395, add=1)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10400, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10402, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10405, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10410, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10415, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10420, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10425, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10430, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10435, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10440, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10446, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10451, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10456, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10461, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10466, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10471, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10476, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10481, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10486, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=10513, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10520, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10527, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10543, add=1)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10547, add=1)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10552, add=1)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10555, add=1)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10560, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10563, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10568, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10573, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10578, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10583, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10588, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10593, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10598, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10604, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10609, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10614, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10619, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10624, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10629, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10634, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10639, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10644, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=10672, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10679, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10686, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10702, add=1)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10706, add=1)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10711, add=1)
        cls.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10714, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10716, add=1)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10719, add=1)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10724, add=0)
        cls.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10726, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10728, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10731, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10736, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10741, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10746, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10751, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10756, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10761, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10766, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10772, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10777, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack, capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10782, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10787, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10792, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack, capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10797, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack, capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10802, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack, capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10807, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack, capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10812, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=10851, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10858, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10865, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10902, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10909, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10916, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10953, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10960, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10967, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11004, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11011, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11018, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11055, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11062, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11069, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11159, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11166, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11173, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11210, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11217, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11224, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11262, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11269, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11276, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11376, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11383, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11390, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11428, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11435, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11442, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11479, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11486, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11493, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11530, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11537, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11544, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11582, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11589, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11596, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11633, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11640, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11647, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11662, add=0)
        self.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=11665, add=1)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11669, add=1)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11674, add=0)
        self.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11676, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11678, add=1)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11681, add=1)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11686, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11688, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11691, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=11718, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11725, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11732, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11748, add=1)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11752, add=1)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11757, add=1)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11760, add=1)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11765, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11768, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=11796, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11803, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11810, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11826, add=1)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11830, add=1)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11835, add=1)
        cls.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11838, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11840, add=1)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11843, add=1)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11848, add=0)
        cls.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11850, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11852, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11855, add=1)
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
update_stack(exp_stack=exp_stack0, line_num=11879, add=0)
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
update_stack(exp_stack=exp_stack0, line_num=11888, add=0)
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
update_stack(exp_stack=exp_stack0, line_num=11905, add=0)
func_get_caller_info_1(exp_stack=exp_stack0, capsys=None)

# call method
cls_get_caller_info01 = ClassGetCallerInfo1()
update_stack(exp_stack=exp_stack0, line_num=11910, add=0)
cls_get_caller_info01.get_caller_info_m1(exp_stack=exp_stack0, capsys=None)

# call static method
update_stack(exp_stack=exp_stack0, line_num=11914, add=0)
cls_get_caller_info01.get_caller_info_s1(exp_stack=exp_stack0, capsys=None)

# call class method
update_stack(exp_stack=exp_stack0, line_num=11918, add=0)
ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack0, capsys=None)

# call overloaded base class method
update_stack(exp_stack=exp_stack0, line_num=11922, add=0)
cls_get_caller_info01.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class static method
update_stack(exp_stack=exp_stack0, line_num=11926, add=0)
cls_get_caller_info01.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class class method
update_stack(exp_stack=exp_stack0, line_num=11930, add=0)
ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call subclass method
cls_get_caller_info01S = ClassGetCallerInfo1S()
update_stack(exp_stack=exp_stack0, line_num=11935, add=0)
cls_get_caller_info01S.get_caller_info_m1s(exp_stack=exp_stack0, capsys=None)

# call subclass static method
update_stack(exp_stack=exp_stack0, line_num=11939, add=0)
cls_get_caller_info01S.get_caller_info_s1s(exp_stack=exp_stack0, capsys=None)

# call subclass class method
update_stack(exp_stack=exp_stack0, line_num=11943, add=0)
ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass method
update_stack(exp_stack=exp_stack0, line_num=11947, add=0)
cls_get_caller_info01S.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass static method
update_stack(exp_stack=exp_stack0, line_num=11951, add=0)
cls_get_caller_info01S.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass class method
update_stack(exp_stack=exp_stack0, line_num=11955, add=0)
ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call base method from subclass method
update_stack(exp_stack=exp_stack0, line_num=11959, add=0)
cls_get_caller_info01S.get_caller_info_m1sb(exp_stack=exp_stack0, capsys=None)

# call base static method from subclass static method
update_stack(exp_stack=exp_stack0, line_num=11963, add=0)
cls_get_caller_info01S.get_caller_info_s1sb(exp_stack=exp_stack0, capsys=None)

# call base class method from subclass class method
update_stack(exp_stack=exp_stack0, line_num=11967, add=0)
ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack0, capsys=None)
