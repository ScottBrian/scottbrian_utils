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
file_arg_list = [None, 'sys.stdout', 'sys.stderr']


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
msg_arg_list = [[None],
                ['one-word'],
                ['two words'],
                ['three + four'],
                ['two', 'items'],
                ['three', 'items', 'for you'],
                ['this', 'has', 'number', 4],
                ['here', 'some', 'math', 4 + 1]]


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
def seq_slice(call_seq: str,
              start: int = 0,
              end: Optional[int] = None
              ) -> str:
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
    seq_items = call_seq.split(' -> ')

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

    ret_seq = ''
    arrow = ' -> '
    for i in range(adj_start, adj_end):
        if i == adj_end - 1:  # if last item
            arrow = ''
        ret_seq = f'{ret_seq}{seq_items[i]}{arrow}'

    return ret_seq


########################################################################
# get_exp_seq is a helper function used by many test cases
########################################################################
def get_exp_seq(exp_stack: Deque[CallerInfo],
                latest: int = 0,
                depth: Optional[int] = None
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
    exp_seq = ''
    arrow = ''
    for i, exp_info in enumerate(reversed(exp_stack)):
        if i < latest:
            continue
        if i == latest + depth:
            break
        if exp_info.func_name:
            dbl_colon = '::'
        else:
            dbl_colon = ''
        if exp_info.cls_name:
            dot = '.'
        else:
            dot = ''

        # # import inspect
        # print('exp_info.line_num:', i, ':', exp_info.line_num)
        # for j in range(5):
        #     frame = _getframe(j)
        #     print(frame.f_code.co_name, ':', frame.f_lineno)

        exp_seq = f'{exp_info.mod_name}{dbl_colon}' \
                  f'{exp_info.cls_name}{dot}{exp_info.func_name}:' \
                  f'{exp_info.line_num}{arrow}{exp_seq}'
        arrow = ' -> '

    return exp_seq


########################################################################
# verify_diag_msg is a helper function used by many test cases
########################################################################
def verify_diag_msg(exp_stack: Deque[CallerInfo],
                    before_time: datetime,
                    after_time: datetime,
                    capsys: pytest.CaptureFixture[str],
                    diag_msg_args: DiagMsgArgs) -> None:
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
        before_time.strftime(diag_msg_args.dt_format_arg),
        diag_msg_args.dt_format_arg)
    after_time = datetime.strptime(
        after_time.strftime(diag_msg_args.dt_format_arg),
        diag_msg_args.dt_format_arg)

    if diag_msg_args.file_arg == 'sys.stdout':
        cap_msg = capsys.readouterr().out
    else:  # must be stderr
        cap_msg = capsys.readouterr().err

    str_list = cap_msg.split()
    dt_format_split_list = diag_msg_args.dt_format_arg.split()
    msg_time_str = ''
    for i in range(len(dt_format_split_list)):
        msg_time_str = f'{msg_time_str}{str_list.pop(0)} '
    msg_time_str = msg_time_str.rstrip()
    msg_time = datetime.strptime(msg_time_str, diag_msg_args.dt_format_arg)

    # if safe to proceed with low resolution
    if before_time <= after_time:
        assert before_time <= msg_time <= after_time

    # build the expected call sequence string
    call_seq = ''
    for i in range(len(str_list)):
        word = str_list.pop(0)
        if i % 2 == 0:  # if even
            if ":" in word:  # if this is a call entry
                call_seq = f'{call_seq}{word}'
            else:  # not a call entry, must be first word of msg
                str_list.insert(0, word)  # put it back
                break  # we are done
        elif word == '->':  # odd and we have arrow
            call_seq = f'{call_seq} {word} '
        else:  # odd and no arrow (beyond call sequence)
            str_list.insert(0, word)  # put it back
            break  # we are done

    verify_call_seq(exp_stack=exp_stack,
                    call_seq=call_seq,
                    seq_depth=diag_msg_args.depth_arg)

    captured_msg = ''
    for i in range(len(str_list)):
        captured_msg = f'{captured_msg}{str_list[i]} '
    captured_msg = captured_msg.rstrip()

    check_msg = ''
    for i in range(len(diag_msg_args.msg_arg)):
        check_msg = f'{check_msg}{diag_msg_args.msg_arg[i]} '
    check_msg = check_msg.rstrip()

    assert captured_msg == check_msg


########################################################################
# verify_call_seq is a helper function used by many test cases
########################################################################
def verify_call_seq(exp_stack: Deque[CallerInfo],
                    call_seq: str,
                    seq_latest: Optional[int] = None,
                    seq_depth: Optional[int] = None) -> None:
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
            call_seq = seq_slice(call_seq=call_seq,
                                 end=len(exp_stack) - seq_latest)

        if len(exp_stack) <= seq_latest + seq_depth:
            assert call_seq == get_exp_seq(exp_stack=exp_stack,
                                           latest=seq_latest)
        else:
            assert call_seq == get_exp_seq(exp_stack=exp_stack,
                                           latest=seq_latest,
                                           depth=seq_depth)


########################################################################
# update stack with new line number
########################################################################
def update_stack(exp_stack: Deque[CallerInfo],
                 line_num: int,
                 add: int) -> None:
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
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='test_get_call_seq_error1',
                                     line_num=420)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=480, add=0)
        call_seq = get_formatted_call_sequence()

        verify_call_seq(exp_stack=exp_stack, call_seq=call_seq)

        call_seq = get_formatted_call_sequence(latest=1000, depth=1001)

        assert call_seq == ''

        save_getframe = sys._getframe
        sys._getframe = None  # type: ignore

        call_seq = get_formatted_call_sequence()

        sys._getframe = save_getframe

        assert call_seq == ''

    ####################################################################
    # Basic test for get_formatted_call_seq
    ####################################################################
    def test_get_call_seq_basic(self) -> None:
        """Test basic get formatted call sequence function."""
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='test_get_call_seq_basic',
                                     line_num=420)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=509, add=0)
        call_seq = get_formatted_call_sequence()

        verify_call_seq(exp_stack=exp_stack, call_seq=call_seq)

    ####################################################################
    # Test with latest and depth parms with stack of 1
    ####################################################################
    def test_get_call_seq_with_parms(self,
                                     latest_arg: Optional[int] = None,
                                     depth_arg: Optional[int] = None
                                     ) -> None:
        """Test get_formatted_call_seq with parms at depth 1.

        Args:
            latest_arg: pytest fixture that specifies how far back into
                          the stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to
                         get

        """
        print('sys.version_info[0]:', sys.version_info[0])
        print('sys.version_info[1]:', sys.version_info[1])
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='test_get_call_seq_with_parms',
                                     line_num=449)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=540, add=0)
        call_seq = ''
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
            call_seq = get_formatted_call_sequence(latest=latest_arg,
                                                   depth=depth_arg)
        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_latest=latest_arg,
                        seq_depth=depth_arg)

        update_stack(exp_stack=exp_stack, line_num=557, add=2)
        self.get_call_seq_depth_2(exp_stack=exp_stack,
                                  latest_arg=latest_arg,
                                  depth_arg=depth_arg)

    ####################################################################
    # Test with latest and depth parms with stack of 2
    ####################################################################
    def get_call_seq_depth_2(self,
                             exp_stack: Deque[CallerInfo],
                             latest_arg: Optional[int] = None,
                             depth_arg: Optional[int] = None
                             ) -> None:
        """Test get_formatted_call_seq at depth 2.

        Args:
            exp_stack: The expected stack of callers
            latest_arg: pytest fixture that specifies how far back into
                          the stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to
                                get

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='get_call_seq_depth_2',
                                     line_num=494)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=587, add=0)
        call_seq = ''
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
            call_seq = get_formatted_call_sequence(latest=latest_arg,
                                                   depth=depth_arg)
        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_latest=latest_arg,
                        seq_depth=depth_arg)

        update_stack(exp_stack=exp_stack, line_num=604, add=2)
        self.get_call_seq_depth_3(exp_stack=exp_stack,
                                  latest_arg=latest_arg,
                                  depth_arg=depth_arg)

        exp_stack.pop()  # return with correct stack

    ####################################################################
    # Test with latest and depth parms with stack of 3
    ####################################################################
    def get_call_seq_depth_3(self,
                             exp_stack: Deque[CallerInfo],
                             latest_arg: Optional[int] = None,
                             depth_arg: Optional[int] = None
                             ) -> None:
        """Test get_formatted_call_seq at depth 3.

        Args:
            exp_stack: The expected stack of callers
            latest_arg: pytest fixture that specifies how far back into
                          the stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to
                         get

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='get_call_seq_depth_3',
                                     line_num=541)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=636, add=0)
        call_seq = ''
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
            call_seq = get_formatted_call_sequence(latest=latest_arg,
                                                   depth=depth_arg)
        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_latest=latest_arg,
                        seq_depth=depth_arg)

        update_stack(exp_stack=exp_stack, line_num=653, add=2)
        self.get_call_seq_depth_4(exp_stack=exp_stack,
                                  latest_arg=latest_arg,
                                  depth_arg=depth_arg)

        exp_stack.pop()  # return with correct stack

    ####################################################################
    # Test with latest and depth parms with stack of 4
    ####################################################################
    def get_call_seq_depth_4(self,
                             exp_stack: Deque[CallerInfo],
                             latest_arg: Optional[int] = None,
                             depth_arg: Optional[int] = None
                             ) -> None:
        """Test get_formatted_call_seq at depth 4.

        Args:
            exp_stack: The expected stack of callers
            latest_arg: pytest fixture that specifies how far back into
                          the stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to
                         get

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='get_call_seq_depth_4',
                                     line_num=588)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=685, add=0)
        call_seq = ''
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
            call_seq = get_formatted_call_sequence(latest=latest_arg,
                                                   depth=depth_arg)
        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_latest=latest_arg,
                        seq_depth=depth_arg)

        exp_stack.pop()  # return with correct stack

    ####################################################################
    # Verify we can run off the end of the stack
    ####################################################################
    def test_get_call_seq_full_stack(self) -> None:
        """Test to ensure we can run the entire stack."""
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='test_get_call_seq_full_stack',
                                     line_num=620)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=718, add=1)
        num_items = 0
        new_count = 1
        while num_items + 1 == new_count:
            call_seq = get_formatted_call_sequence(latest=0,
                                                   depth=new_count)
            call_seq_list = call_seq.split()
            # The call_seq_list will have x call items and x-1 arrows,
            # so the following code will calculate the number of items
            # by adding 1 more arrow and dividing the sum by 2
            num_items = (len(call_seq_list) + 1)//2
            verify_call_seq(exp_stack=exp_stack,
                            call_seq=call_seq,
                            seq_latest=0,
                            seq_depth=num_items)
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
    def get_diag_msg_args(*,
                          dt_format_arg: Optional[str] = None,
                          depth_arg: Optional[int] = None,
                          msg_arg: Optional[List[Union[str, int]]] = None,
                          file_arg: Optional[str] = None
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

        a_msg_arg: List[Union[str, int]] = ['']
        if msg_arg is not None:
            a_arg_bits = a_arg_bits | TestDiagMsg.MSG1
            a_msg_arg = msg_arg

        a_file_arg = 'sys.stdout'
        if file_arg is not None:
            a_arg_bits = a_arg_bits | TestDiagMsg.FILE1
            a_file_arg = file_arg

        return DiagMsgArgs(arg_bits=a_arg_bits,
                           dt_format_arg=a_dt_format_arg,
                           depth_arg=a_depth_arg,
                           msg_arg=a_msg_arg,
                           file_arg=a_file_arg)

    ####################################################################
    # Basic diag_msg test
    ####################################################################
    def test_diag_msg_basic(self,
                            capsys: pytest.CaptureFixture[str]) -> None:
        """Test various combinations of msg_diag.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestDiagMsg',
                                     func_name='test_diag_msg_basic',
                                     line_num=727)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=829, add=0)
        before_time = datetime.now()
        diag_msg()
        after_time = datetime.now()

        diag_msg_args = self.get_diag_msg_args()
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

    ####################################################################
    # diag_msg with parms
    ####################################################################
    def test_diag_msg_with_parms(self,
                                 capsys: pytest.CaptureFixture[str],
                                 dt_format_arg: str,
                                 depth_arg: int,
                                 msg_arg: List[Union[str, int]],
                                 file_arg: str) -> None:
        """Test various combinations of msg_diag.

        Args:
            capsys: pytest fixture that captures output
            dt_format_arg: pytest fixture for datetime format
            depth_arg: pytest fixture for number of call seq entries
            msg_arg: pytest fixture for messages
            file_arg: pytest fixture for different print file types

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestDiagMsg',
                                     func_name='test_diag_msg_with_parms',
                                     line_num=768)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=871, add=0)
        diag_msg_args = self.get_diag_msg_args(dt_format_arg=dt_format_arg,
                                               depth_arg=depth_arg,
                                               msg_arg=msg_arg,
                                               file_arg=file_arg)
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
            diag_msg(*diag_msg_args.msg_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=884, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=887, add=1)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=891, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=895, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=900, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=903, add=1)
            diag_msg(dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=907, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=911, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=916, add=1)
            diag_msg(depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=920, add=2)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg),
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=925, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=930, add=3)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))

        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        update_stack(exp_stack=exp_stack, line_num=944, add=2)
        self.diag_msg_depth_2(exp_stack=exp_stack,
                              capsys=capsys,
                              diag_msg_args=diag_msg_args)

    ####################################################################
    # Depth 2 test
    ####################################################################
    def diag_msg_depth_2(self,
                         exp_stack: Deque[CallerInfo],
                         capsys: pytest.CaptureFixture[str],
                         diag_msg_args: DiagMsgArgs) -> None:
        """Test msg_diag with two callers in the sequence.

        Args:
            exp_stack: The expected stack as modified by each test case
            capsys: pytest fixture that captures output
            diag_msg_args: Specifies the args to use on the diag_msg
                             invocation

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestDiagMsg',
                                     func_name='diag_msg_depth_2',
                                     line_num=867)
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
            diag_msg(*diag_msg_args.msg_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=985, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=988, add=1)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=992, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=996, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1001, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1004, add=1)
            diag_msg(dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1008, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1012, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1017, add=1)
            diag_msg(depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1021, add=2)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg),
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1026, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1031, add=3)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))

        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        update_stack(exp_stack=exp_stack, line_num=1045, add=2)
        self.diag_msg_depth_3(exp_stack=exp_stack,
                              capsys=capsys,
                              diag_msg_args=diag_msg_args)

        exp_stack.pop()  # return with correct stack

    ####################################################################
    # Depth 3 test
    ####################################################################
    def diag_msg_depth_3(self,
                         exp_stack: Deque[CallerInfo],
                         capsys: pytest.CaptureFixture[str],
                         diag_msg_args: DiagMsgArgs) -> None:
        """Test msg_diag with three callers in the sequence.

        Args:
            exp_stack: The expected stack as modified by each test case
            capsys: pytest fixture that captures output
            diag_msg_args: Specifies the args to use on the diag_msg
                             invocation

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestDiagMsg',
                                     func_name='diag_msg_depth_3',
                                     line_num=968)
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
            diag_msg(*diag_msg_args.msg_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1088, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1091, add=1)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1095, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1099, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1104, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1107, add=1)
            diag_msg(dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1111, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1115, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1120, add=1)
            diag_msg(depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1124, add=2)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg),
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1129, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1134, add=3)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))

        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

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
    exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                 cls_name='',
                                 func_name='test_func_get_caller_info_0',
                                 line_num=1071)
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
    diag_msg('message 0', 0, depth=1)
    after_time = datetime.now()

    diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                  msg_arg=['message 0', 0])
    verify_diag_msg(exp_stack=exp_stack,
                    before_time=before_time,
                    after_time=after_time,
                    capsys=capsys,
                    diag_msg_args=diag_msg_args)

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
    cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=1228, add=1)
    cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=1233, add=1)
    ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info1s = ClassGetCallerInfo1S()
    update_stack(exp_stack=exp_stack, line_num=1239, add=1)
    cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=1244, add=1)
    cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=1249, add=1)
    ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=1254, add=1)
    cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=1259, add=1)
    cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=1264, add=1)
    ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=1269, add=1)
    cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=1274, add=1)
    cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=1279, add=1)
    ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                              capsys=capsys)

    ####################################################################
    # Inner class defined inside function test_func_get_caller_info_0
    ####################################################################
    class Inner:
        """Inner class for testing with inner class."""

        def __init__(self) -> None:
            """Initialize Inner class object."""
            self.var2 = 2

        def g1(self,
               exp_stack_g: Deque[CallerInfo],
               capsys_g: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_g: The expected call stack
                capsys_g: Pytest fixture that captures output

            """
            exp_caller_info_g = CallerInfo(mod_name='test_diag_msg.py',
                                           cls_name='Inner',
                                           func_name='g1',
                                           line_num=1197)
            exp_stack_g.append(exp_caller_info_g)
            update_stack(exp_stack=exp_stack_g, line_num=1312, add=0)
            for i_g, expected_caller_info_g in enumerate(
                    list(reversed(exp_stack_g))):
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
                diag_msg('message 1', 1, depth=len(exp_stack_g))
                after_time_g = datetime.now()

                diag_msg_args_g = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_g),
                    msg_arg=['message 1', 1])
                verify_diag_msg(exp_stack=exp_stack_g,
                                before_time=before_time_g,
                                after_time=after_time_g,
                                capsys=capsys_g,
                                diag_msg_args=diag_msg_args_g)

            # call module level function
            update_stack(exp_stack=exp_stack_g, line_num=1341, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1346, add=1)
            cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1351, add=1)
            cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1356, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack_g,
                                                   capsys=capsys_g)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1361, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1366, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1371, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1377, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1382, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1387, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1392, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1397, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1402, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1407, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1412, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1417, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            exp_stack.pop()

        @staticmethod
        def g2_static(exp_stack_g: Deque[CallerInfo],
                      capsys_g: Optional[Any]) -> None:
            """Inner static method to test diag msg.

            Args:
                exp_stack_g: The expected call stack
                capsys_g: Pytest fixture that captures output

            """
            exp_caller_info_g = CallerInfo(mod_name='test_diag_msg.py',
                                           cls_name='Inner',
                                           func_name='g2_static',
                                           line_num=1197)
            exp_stack_g.append(exp_caller_info_g)
            update_stack(exp_stack=exp_stack_g, line_num=1442, add=0)
            for i_g, expected_caller_info_g in enumerate(
                    list(reversed(exp_stack_g))):
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
                diag_msg('message 1', 1, depth=len(exp_stack_g))
                after_time_g = datetime.now()

                diag_msg_args_g = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_g),
                    msg_arg=['message 1', 1])
                verify_diag_msg(exp_stack=exp_stack_g,
                                before_time=before_time_g,
                                after_time=after_time_g,
                                capsys=capsys_g,
                                diag_msg_args=diag_msg_args_g)

            # call module level function
            update_stack(exp_stack=exp_stack_g, line_num=1471, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1476, add=1)
            cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1481, add=1)
            cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1486, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack_g,
                                                   capsys=capsys_g)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1491, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1496, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1501, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1507, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1512, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1517, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1522, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1527, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1532, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1537, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1542, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1547, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            exp_stack.pop()

        @classmethod
        def g3_class(cls,
                     exp_stack_g: Deque[CallerInfo],
                     capsys_g: Optional[Any]) -> None:
            """Inner class method to test diag msg.

            Args:
                exp_stack_g: The expected call stack
                capsys_g: Pytest fixture that captures output

            """
            exp_caller_info_g = CallerInfo(mod_name='test_diag_msg.py',
                                           cls_name='Inner',
                                           func_name='g3_class',
                                           line_num=1197)
            exp_stack_g.append(exp_caller_info_g)
            update_stack(exp_stack=exp_stack_g, line_num=1573, add=0)
            for i_g, expected_caller_info_g in enumerate(
                    list(reversed(exp_stack_g))):
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
                diag_msg('message 1', 1, depth=len(exp_stack_g))
                after_time_g = datetime.now()

                diag_msg_args_g = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_g),
                    msg_arg=['message 1', 1])
                verify_diag_msg(exp_stack=exp_stack_g,
                                before_time=before_time_g,
                                after_time=after_time_g,
                                capsys=capsys_g,
                                diag_msg_args=diag_msg_args_g)

            # call module level function
            update_stack(exp_stack=exp_stack_g, line_num=1602, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1607, add=1)
            cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1612, add=1)
            cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1617, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack_g,
                                                   capsys=capsys_g)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1622, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1627, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1632, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1638, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1643, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1648, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1653, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1658, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1663, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1668, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1673, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1678, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            exp_stack.pop()

    class Inherit(Inner):
        """Inherit class for testing inner class."""

        def __init__(self) -> None:
            """Initialize Inherit object."""
            super().__init__()
            self.var3 = 3

        def h1(self,
               exp_stack_h: Deque[CallerInfo],
               capsys_h: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_h: The expected call stack
                capsys_h: Pytest fixture that captures output

            """
            exp_caller_info_h = CallerInfo(mod_name='test_diag_msg.py',
                                           cls_name='Inherit',
                                           func_name='h1',
                                           line_num=1197)
            exp_stack_h.append(exp_caller_info_h)
            update_stack(exp_stack=exp_stack_h, line_num=1711, add=0)
            for i_h, expected_caller_info_h in enumerate(
                    list(reversed(exp_stack_h))):
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
                diag_msg('message 1', 1, depth=len(exp_stack_h))
                after_time_h = datetime.now()

                diag_msg_args_h = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_h),
                    msg_arg=['message 1', 1])
                verify_diag_msg(exp_stack=exp_stack_h,
                                before_time=before_time_h,
                                after_time=after_time_h,
                                capsys=capsys_h,
                                diag_msg_args=diag_msg_args_h)

            # call module level function
            update_stack(exp_stack=exp_stack_h, line_num=1740, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=1745, add=1)
            cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=1750, add=1)
            cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=1755, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack_h,
                                                   capsys=capsys_h)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=1760, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=1765, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=1770, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=1776, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1781, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1786, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1791, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1796, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1801, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1806, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1811, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1816, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            exp_stack.pop()

        @staticmethod
        def h2_static(exp_stack_h: Deque[CallerInfo],
                      capsys_h: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_h: The expected call stack
                capsys_h: Pytest fixture that captures output

            """
            exp_caller_info_h = CallerInfo(mod_name='test_diag_msg.py',
                                           cls_name='Inherit',
                                           func_name='h2_static',
                                           line_num=1197)
            exp_stack_h.append(exp_caller_info_h)
            update_stack(exp_stack=exp_stack_h, line_num=1841, add=0)
            for i_h, expected_caller_info_h in enumerate(
                    list(reversed(exp_stack_h))):
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
                diag_msg('message 1', 1, depth=len(exp_stack_h))
                after_time_h = datetime.now()

                diag_msg_args_h = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_h),
                    msg_arg=['message 1', 1])
                verify_diag_msg(exp_stack=exp_stack_h,
                                before_time=before_time_h,
                                after_time=after_time_h,
                                capsys=capsys_h,
                                diag_msg_args=diag_msg_args_h)

            # call module level function
            update_stack(exp_stack=exp_stack_h, line_num=1870, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=1875, add=1)
            cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=1880, add=1)
            cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=1885, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack_h,
                                                   capsys=capsys_h)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=1890, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=1895, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=1900, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=1906, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1911, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1916, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1921, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1926, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1931, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1936, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1941, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1946, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            exp_stack.pop()

        @classmethod
        def h3_class(cls,
                     exp_stack_h: Deque[CallerInfo],
                     capsys_h: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_h: The expected call stack
                capsys_h: Pytest fixture that captures output

            """
            exp_caller_info_h = CallerInfo(mod_name='test_diag_msg.py',
                                           cls_name='Inherit',
                                           func_name='h3_class',
                                           line_num=1197)
            exp_stack_h.append(exp_caller_info_h)
            update_stack(exp_stack=exp_stack_h, line_num=1972, add=0)
            for i_h, expected_caller_info_h in enumerate(
                    list(reversed(exp_stack_h))):
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
                diag_msg('message 1', 1, depth=len(exp_stack_h))
                after_time_h = datetime.now()

                diag_msg_args_h = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_h),
                    msg_arg=['message 1', 1])
                verify_diag_msg(exp_stack=exp_stack_h,
                                before_time=before_time_h,
                                after_time=after_time_h,
                                capsys=capsys_h,
                                diag_msg_args=diag_msg_args_h)

            # call module level function
            update_stack(exp_stack=exp_stack_h, line_num=2001, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=2006, add=1)
            cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2011, add=1)
            cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2016, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack_h,
                                                   capsys=capsys_h)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2021, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2026, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2031, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=2037, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2042, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2047, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2052, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2057, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2062, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2067, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2072, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2077, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

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
def func_get_caller_info_1(exp_stack: Deque[CallerInfo],
                           capsys: Optional[Any]) -> None:
    """Module level function 1 to test get_caller_info.

    Args:
        exp_stack: The expected call stack
        capsys: Pytest fixture that captures output

    """
    exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                 cls_name='',
                                 func_name='func_get_caller_info_1',
                                 line_num=1197)
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
        diag_msg('message 1', 1, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=len(exp_stack),
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

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
    cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=2178, add=1)
    cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=2183, add=1)
    ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info2s = ClassGetCallerInfo2S()
    update_stack(exp_stack=exp_stack, line_num=2189, add=1)
    cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=2194, add=1)
    cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=2199, add=1)
    ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=2204, add=1)
    cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=2209, add=1)
    cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=2214, add=1)
    ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=2219, add=1)
    cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=2224, add=1)
    cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=2229, add=1)
    ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                              capsys=capsys)

    ####################################################################
    # Inner class defined inside function test_func_get_caller_info_0
    ####################################################################
    class Inner:
        """Inner class for testing with inner class."""
        def __init__(self) -> None:
            """Initialize Inner class object."""
            self.var2 = 2

        def g1(self,
               exp_stack_g: Deque[CallerInfo],
               capsys_g: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_g: The expected call stack
                capsys_g: Pytest fixture that captures output

            """
            exp_caller_info_g = CallerInfo(mod_name='test_diag_msg.py',
                                           cls_name='Inner',
                                           func_name='g1',
                                           line_num=1197)
            exp_stack_g.append(exp_caller_info_g)
            update_stack(exp_stack=exp_stack_g, line_num=2261, add=0)
            for i_g, expected_caller_info_g in enumerate(
                    list(reversed(exp_stack_g))):
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
                diag_msg('message 1', 1, depth=len(exp_stack_g))
                after_time_g = datetime.now()

                diag_msg_args_g = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_g),
                    msg_arg=['message 1', 1])
                verify_diag_msg(exp_stack=exp_stack_g,
                                before_time=before_time_g,
                                after_time=after_time_g,
                                capsys=capsys_g,
                                diag_msg_args=diag_msg_args_g)

            # call module level function
            update_stack(exp_stack=exp_stack_g, line_num=2290, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2295, add=1)
            cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2300, add=1)
            cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2305, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack_g,
                                                   capsys=capsys_g)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2310, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2315, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2320, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2326, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2331, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2336, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2341, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2346, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2351, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2356, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2361, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2366, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            exp_stack.pop()

        @staticmethod
        def g2_static(exp_stack_g: Deque[CallerInfo],
                      capsys_g: Optional[Any]) -> None:
            """Inner static method to test diag msg.

            Args:
                exp_stack_g: The expected call stack
                capsys_g: Pytest fixture that captures output

            """
            exp_caller_info_g = CallerInfo(mod_name='test_diag_msg.py',
                                           cls_name='Inner',
                                           func_name='g2_static',
                                           line_num=2297)
            exp_stack_g.append(exp_caller_info_g)
            update_stack(exp_stack=exp_stack_g, line_num=2391, add=0)
            for i_g, expected_caller_info_g in enumerate(
                    list(reversed(exp_stack_g))):
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
                diag_msg('message 1', 1, depth=len(exp_stack_g))
                after_time_g = datetime.now()

                diag_msg_args_g = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_g),
                    msg_arg=['message 1', 1])
                verify_diag_msg(exp_stack=exp_stack_g,
                                before_time=before_time_g,
                                after_time=after_time_g,
                                capsys=capsys_g,
                                diag_msg_args=diag_msg_args_g)

            # call module level function
            update_stack(exp_stack=exp_stack_g, line_num=2420, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2425, add=1)
            cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2430, add=1)
            cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2435, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack_g,
                                                   capsys=capsys_g)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2440, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2445, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2450, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2456, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2461, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2466, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2471, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2476, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2481, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2486, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2491, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2496, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            exp_stack.pop()

        @classmethod
        def g3_class(cls,
                     exp_stack_g: Deque[CallerInfo],
                     capsys_g: Optional[Any]) -> None:
            """Inner class method to test diag msg.

            Args:
                exp_stack_g: The expected call stack
                capsys_g: Pytest fixture that captures output

            """
            exp_caller_info_g = CallerInfo(mod_name='test_diag_msg.py',
                                           cls_name='Inner',
                                           func_name='g3_class',
                                           line_num=2197)
            exp_stack_g.append(exp_caller_info_g)
            update_stack(exp_stack=exp_stack_g, line_num=2522, add=0)
            for i_g, expected_caller_info_g in enumerate(
                    list(reversed(exp_stack_g))):
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
                diag_msg('message 1', 1, depth=len(exp_stack_g))
                after_time_g = datetime.now()

                diag_msg_args_g = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_g),
                    msg_arg=['message 1', 1])
                verify_diag_msg(exp_stack=exp_stack_g,
                                before_time=before_time_g,
                                after_time=after_time_g,
                                capsys=capsys_g,
                                diag_msg_args=diag_msg_args_g)

            # call module level function
            update_stack(exp_stack=exp_stack_g, line_num=2551, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2556, add=1)
            cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2561, add=1)
            cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2566, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack_g,
                                                   capsys=capsys_g)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2571, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2576, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2581, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2587, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2592, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2597, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2602, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2607, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2612, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2617, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2622, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2627, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            exp_stack.pop()

    class Inherit(Inner):
        """Inherit class for testing inner class."""
        def __init__(self) -> None:
            """Initialize Inherit object."""
            super().__init__()
            self.var3 = 3

        def h1(self,
               exp_stack_h: Deque[CallerInfo],
               capsys_h: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_h: The expected call stack
                capsys_h: Pytest fixture that captures output

            """
            exp_caller_info_h = CallerInfo(mod_name='test_diag_msg.py',
                                           cls_name='Inherit',
                                           func_name='h1',
                                           line_num=1197)
            exp_stack_h.append(exp_caller_info_h)
            update_stack(exp_stack=exp_stack_h, line_num=2659, add=0)
            for i_h, expected_caller_info_h in enumerate(
                    list(reversed(exp_stack_h))):
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
                diag_msg('message 1', 1, depth=len(exp_stack_h))
                after_time_h = datetime.now()

                diag_msg_args_h = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_h),
                    msg_arg=['message 1', 1])
                verify_diag_msg(exp_stack=exp_stack_h,
                                before_time=before_time_h,
                                after_time=after_time_h,
                                capsys=capsys_h,
                                diag_msg_args=diag_msg_args_h)

            # call module level function
            update_stack(exp_stack=exp_stack_h, line_num=2688, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2693, add=1)
            cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2698, add=1)
            cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2703, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack_h,
                                                   capsys=capsys_h)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2708, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2713, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2718, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=2724, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2729, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2734, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2739, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2744, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2749, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2754, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2759, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2764, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            exp_stack.pop()

        @staticmethod
        def h2_static(exp_stack_h: Deque[CallerInfo],
                      capsys_h: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_h: The expected call stack
                capsys_h: Pytest fixture that captures output

            """
            exp_caller_info_h = CallerInfo(mod_name='test_diag_msg.py',
                                           cls_name='Inherit',
                                           func_name='h2_static',
                                           line_num=1197)
            exp_stack_h.append(exp_caller_info_h)
            update_stack(exp_stack=exp_stack_h, line_num=2789, add=0)
            for i_h, expected_caller_info_h in enumerate(
                    list(reversed(exp_stack_h))):
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
                diag_msg('message 1', 1, depth=len(exp_stack_h))
                after_time_h = datetime.now()

                diag_msg_args_h = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_h),
                    msg_arg=['message 1', 1])
                verify_diag_msg(exp_stack=exp_stack_h,
                                before_time=before_time_h,
                                after_time=after_time_h,
                                capsys=capsys_h,
                                diag_msg_args=diag_msg_args_h)

            # call module level function
            update_stack(exp_stack=exp_stack_h, line_num=2818, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2823, add=1)
            cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2828, add=1)
            cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2833, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack_h,
                                                   capsys=capsys_h)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2838, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2843, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2848, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=2854, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2859, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2864, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2869, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2874, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2879, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2884, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2889, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2894, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            exp_stack.pop()

        @classmethod
        def h3_class(cls,
                     exp_stack_h: Deque[CallerInfo],
                     capsys_h: Optional[Any]) -> None:
            """Inner method to test diag msg.

            Args:
                exp_stack_h: The expected call stack
                capsys_h: Pytest fixture that captures output

            """
            exp_caller_info_h = CallerInfo(mod_name='test_diag_msg.py',
                                           cls_name='Inherit',
                                           func_name='h3_class',
                                           line_num=1197)
            exp_stack_h.append(exp_caller_info_h)
            update_stack(exp_stack=exp_stack_h, line_num=2920, add=0)
            for i_h, expected_caller_info_h in enumerate(
                    list(reversed(exp_stack_h))):
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
                diag_msg('message 1', 1, depth=len(exp_stack_h))
                after_time_h = datetime.now()

                diag_msg_args_h = TestDiagMsg.get_diag_msg_args(
                    depth_arg=len(exp_stack_h),
                    msg_arg=['message 1', 1])
                verify_diag_msg(exp_stack=exp_stack_h,
                                before_time=before_time_h,
                                after_time=after_time_h,
                                capsys=capsys_h,
                                diag_msg_args=diag_msg_args_h)

            # call module level function
            update_stack(exp_stack=exp_stack_h, line_num=2949, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2954, add=1)
            cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2959, add=1)
            cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2964, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack_h,
                                                   capsys=capsys_h)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2969, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2974, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2979, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=2985, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2990, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2995, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3000, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3005, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3010, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=3015, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=3020, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=3025, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

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
def func_get_caller_info_2(exp_stack: Deque[CallerInfo],
                           capsys: Optional[Any]) -> None:
    """Module level function 1 to test get_caller_info.

    Args:
        exp_stack: The expected call stack
        capsys: Pytest fixture that captures output

    """
    exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                 cls_name='',
                                 func_name='func_get_caller_info_2',
                                 line_num=1324)
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
        diag_msg('message 2', 2, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=len(exp_stack),
                                                      msg_arg=['message 2', 2])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

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
    cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=3126, add=1)
    cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=3131, add=1)
    ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info3s = ClassGetCallerInfo3S()
    update_stack(exp_stack=exp_stack, line_num=3137, add=1)
    cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=3142, add=1)
    cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=3147, add=1)
    ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=3152, add=1)
    cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=3157, add=1)
    cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=3162, add=1)
    ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=3167, add=1)
    cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=3172, add=1)
    cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=3177, add=1)
    ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                              capsys=capsys)

    exp_stack.pop()


########################################################################
# func 3
########################################################################
def func_get_caller_info_3(exp_stack: Deque[CallerInfo],
                           capsys: Optional[Any]) -> None:
    """Module level function 1 to test get_caller_info.

    Args:
        exp_stack: The expected call stack
        capsys: Pytest fixture that captures output

    """
    exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                 cls_name='',
                                 func_name='func_get_caller_info_3',
                                 line_num=1451)
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
        diag_msg('message 2', 2, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=len(exp_stack),
                                                      msg_arg=['message 2', 2])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

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
    def test_get_caller_info_m0(self,
                                capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info method 1.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_m0',
                                     line_num=1509)
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
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=3290, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3295, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3300, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3305, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3310, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3315, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3320, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3326, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3331, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3336, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3341, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3346, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3351, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3356, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3361, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3366, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 2
    ####################################################################
    def test_get_caller_info_helper(self,
                                    capsys: pytest.CaptureFixture[str]
                                    ) -> None:
        """Get capsys for static methods.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_helper',
                                     line_num=1635)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=3390, add=0)
        self.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3392, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0(exp_stack=exp_stack,
                                                   capsys=capsys)

        update_stack(exp_stack=exp_stack, line_num=3396, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3398, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)

    @staticmethod
    def get_caller_info_s0(exp_stack: Deque[CallerInfo],
                           capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info static method 0.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='get_caller_info_s0',
                                     line_num=1664)
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
        diag_msg('message 1', 1, depth=2)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=2,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=3447, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3452, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3457, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3462, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3467, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3472, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3477, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3483, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3488, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3493, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3498, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3503, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3508, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3513, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3518, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3523, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 3
    ####################################################################
    @classmethod
    def test_get_caller_info_c0(cls,
                                capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info class method 0.

        Args:
            capsys: Pytest fixture that captures output
        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_c0',
                                     line_num=1792)
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
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=3576, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3581, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3586, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3591, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3596, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3601, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3606, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3612, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3617, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3622, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3627, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3632, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3637, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3642, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3647, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3652, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 4
    ####################################################################
    def test_get_caller_info_m0bo(self,
                                  capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_m0bo',
                                     line_num=1920)
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
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=3705, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3710, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3715, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3720, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3725, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3730, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3735, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3741, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3746, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3751, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3756, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3761, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3766, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3771, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3776, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3781, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

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
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_s0bo',
                                     line_num=2048)
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
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=3834, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3839, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3844, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3849, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3854, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3859, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3864, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3870, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3875, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3880, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3885, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3890, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3895, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3900, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3905, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3910, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 6
    ####################################################################
    @classmethod
    def test_get_caller_info_c0bo(cls,
                                  capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_c0bo',
                                     line_num=2177)
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
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=3964, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3969, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3974, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3979, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3984, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3989, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3994, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4000, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4005, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4010, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4015, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4020, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4025, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4030, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4035, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4040, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 7
    ####################################################################
    def test_get_caller_info_m0bt(self,
                                  capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_m0bt',
                                     line_num=2305)
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
        diag_msg('message 1', 1, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=len(exp_stack),
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4093, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4098, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4103, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4108, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4113, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4118, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4123, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4129, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4134, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4139, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4144, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4149, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4154, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4159, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4164, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4169, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s0bt(exp_stack: Deque[CallerInfo],
                             capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded static method 0.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='get_caller_info_s0bt',
                                     line_num=2434)
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
        diag_msg('message 1', 1, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=len(exp_stack),
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4223, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4228, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4233, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4238, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4243, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4248, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4253, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4259, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4264, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4269, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4274, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4279, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4284, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4289, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4294, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4299, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0 Method 9
    ####################################################################
    @classmethod
    def test_get_caller_info_c0bt(cls,
                                  exp_stack: Optional[Deque[CallerInfo]],
                                  capsys: pytest.CaptureFixture[str]
                                  ) -> None:
        """Get caller info overloaded class method 0.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        if not exp_stack:
            exp_stack = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_c0bt',
                                     line_num=2567)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4330, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4337, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4344, add=0)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=len(exp_stack))
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=len(exp_stack),
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4357, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4362, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4367, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4372, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4377, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4382, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4387, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4393, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4398, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4403, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4408, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4413, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4418, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4423, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4428, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4433, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


########################################################################
# Class 0S
########################################################################
class TestClassGetCallerInfo0S(TestClassGetCallerInfo0):
    """Subclass to get caller info0."""

    ####################################################################
    # Class 0S Method 1
    ####################################################################
    def test_get_caller_info_m0s(self,
                                 capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info method 0.

        Args:
            capsys: Pytest fixture that captures output
        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_m0s',
                                     line_num=2701)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4465, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4472, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4479, add=0)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4492, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4497, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4502, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4507, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4512, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4517, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4522, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4528, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4533, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4538, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4543, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4548, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4553, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4558, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4563, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4568, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

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
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_s0s',
                                     line_num=2829)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4594, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4601, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4608, add=0)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4621, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4626, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4631, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4636, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4641, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4646, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4651, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4657, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4662, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4667, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4672, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4677, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4682, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4687, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4692, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4697, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 3
    ####################################################################
    @classmethod
    def test_get_caller_info_c0s(cls,
                                 capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_c0s',
                                     line_num=2958)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4724, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4731, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4738, add=0)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4751, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4756, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4761, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4766, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4771, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4776, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4781, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4787, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4792, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4797, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4802, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4807, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4812, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4817, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4822, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4827, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 4
    ####################################################################
    def test_get_caller_info_m0bo(self,
                                  capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_m0bo',
                                     line_num=3086)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4853, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4860, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4867, add=0)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=4880, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4885, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4890, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4895, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4900, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4905, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4910, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4916, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4921, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4926, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4931, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4936, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4941, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4946, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4951, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4956, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

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
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_s0bo',
                                     line_num=3214)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=4982, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4989, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4996, add=0)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5009, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5014, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5019, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5024, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5029, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5034, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5039, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5045, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5050, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5055, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5060, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5065, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5070, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5075, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5080, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5085, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 6
    ####################################################################
    @classmethod
    def test_get_caller_info_c0bo(cls,
                                  capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_c0bo',
                                     line_num=3343)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5112, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5119, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5126, add=0)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5139, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5144, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5149, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5154, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5159, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5164, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5169, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5175, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5180, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5185, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5190, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5195, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5200, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5205, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5210, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5215, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 7
    ####################################################################
    def test_get_caller_info_m0sb(self,
                                  capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_m0sb',
                                     line_num=3471)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5241, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5248, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5255, add=0)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call base class normal method target
        update_stack(exp_stack=exp_stack, line_num=5268, add=0)
        self.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        update_stack(exp_stack=exp_stack, line_num=5271, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5274, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5278, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5280, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5282, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5285, add=1)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5290, add=0)
        super().test_get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5292, add=1)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5295, add=1)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5300, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5305, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5310, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5315, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5320, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5325, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5330, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5336, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5341, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5346, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5351, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5356, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5361, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5366, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5371, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5376, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

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
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_s0sb',
                                     line_num=3631)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5402, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5409, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5416, add=0)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call base class normal method target
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        update_stack(exp_stack=exp_stack, line_num=5430, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5433, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5437, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5440, add=1)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5445, add=1)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5448, add=1)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5453, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5458, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5463, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5468, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5473, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5478, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5483, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5489, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5494, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5499, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5504, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5509, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5514, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5519, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5524, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5529, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 0S Method 9
    ####################################################################
    @classmethod
    def test_get_caller_info_c0sb(cls,
                                  capsys: pytest.CaptureFixture[str]) -> None:
        """Get caller info overloaded class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_c0sb',
                                     line_num=3784)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5556, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5563, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5570, add=0)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        diag_msg_args = TestDiagMsg.get_diag_msg_args(depth_arg=1,
                                                      msg_arg=['message 1', 1])
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

        # call base class normal method target
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        update_stack(exp_stack=exp_stack, line_num=5584, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5587, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5591, add=1)
        cls.get_caller_info_s0bt(exp_stack=exp_stack,
                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5594, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5596, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5599, add=1)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)
        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5603, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5608, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5613, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5618, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5623, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5628, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5633, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5639, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5644, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5649, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5654, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5659, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5664, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5669, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5674, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5679, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

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
    def get_caller_info_m1(self,
                           exp_stack: Deque[CallerInfo],
                           capsys: Optional[Any]) -> None:
        """Get caller info method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        self.var1 += 1
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1',
                                     func_name='get_caller_info_m1',
                                     line_num=3945)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5718, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5725, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=5732, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5747, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=5752, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5757, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5762, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5767, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5772, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5777, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=5783, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5788, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5793, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5798, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5803, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5808, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5813, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5818, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5823, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 2
    ####################################################################
    @staticmethod
    def get_caller_info_s1(exp_stack: Deque[CallerInfo],
                           capsys: Optional[Any]) -> None:
        """Get caller info static method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1',
                                     func_name='get_caller_info_s1',
                                     line_num=4076)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5850, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5857, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=5864, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5879, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=5884, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5889, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5894, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5899, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5904, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5909, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=5915, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5920, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5925, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5930, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5935, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5940, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5945, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5950, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5955, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 3
    ####################################################################
    @classmethod
    def get_caller_info_c1(cls,
                           exp_stack: Deque[CallerInfo],
                           capsys: Optional[Any]) -> None:
        """Get caller info class method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output
        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1',
                                     func_name='get_caller_info_c1',
                                     line_num=4207)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=5982, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5989, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=5996, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6011, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6016, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6021, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6026, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6031, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6036, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6041, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6047, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6052, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6057, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6062, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6067, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6072, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6077, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6082, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6087, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 4
    ####################################################################
    def get_caller_info_m1bo(self,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1',
                                     func_name='get_caller_info_m1bo',
                                     line_num=4338)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6114, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6121, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6128, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6143, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6148, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6153, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6158, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6163, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6168, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6173, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6179, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6184, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6189, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6194, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6199, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6204, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6209, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6214, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6219, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 5
    ####################################################################
    @staticmethod
    def get_caller_info_s1bo(exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded static method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1',
                                     func_name='get_caller_info_s1bo',
                                     line_num=4469)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6246, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6253, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6260, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6275, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6280, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6285, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6290, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6295, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6300, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6305, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6311, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6316, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6321, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6326, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6331, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6336, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6341, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6346, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6351, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 6
    ####################################################################
    @classmethod
    def get_caller_info_c1bo(cls,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded class method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1',
                                     func_name='get_caller_info_c1bo',
                                     line_num=4601)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6379, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6386, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6393, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6408, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6413, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6418, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6423, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6428, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6433, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6438, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6444, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6449, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6454, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6459, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6464, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6469, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6474, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6479, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6484, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 7
    ####################################################################
    def get_caller_info_m1bt(self,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        self.var1 += 1
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1',
                                     func_name='get_caller_info_m1bt',
                                     line_num=4733)
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
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6541, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6546, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6551, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6556, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6561, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6566, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6571, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6577, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6582, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6587, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6592, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6597, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6602, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6607, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6612, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6617, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s1bt(exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded static method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1',
                                     func_name='get_caller_info_s1bt',
                                     line_num=4864)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6644, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6651, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6658, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6673, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6678, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6683, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6688, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6693, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6698, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6703, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6709, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6714, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6719, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6724, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6729, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6734, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6739, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6744, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6749, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1 Method 9
    ####################################################################
    @classmethod
    def get_caller_info_c1bt(cls,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded class method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1',
                                     func_name='get_caller_info_c1bt',
                                     line_num=4996)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6777, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6784, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6791, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6806, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6811, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6816, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6821, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6826, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6831, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6836, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6842, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6847, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6852, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6857, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6862, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6867, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6872, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6877, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6882, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

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
    def get_caller_info_m1s(self,
                            exp_stack: Deque[CallerInfo],
                            capsys: Optional[Any]) -> None:
        """Get caller info method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output
        """
        self.var1 += 1
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1S',
                                     func_name='get_caller_info_m1s',
                                     line_num=5139)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=6921, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6928, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6935, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=6950, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6955, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6960, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6965, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6970, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6975, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6980, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6986, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6991, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6996, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7001, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7006, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7011, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7016, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7021, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7026, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 2
    ####################################################################
    @staticmethod
    def get_caller_info_s1s(exp_stack: Deque[CallerInfo],
                            capsys: Optional[Any]) -> None:
        """Get caller info static method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1S',
                                     func_name='get_caller_info_s1s',
                                     line_num=5270)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7053, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7060, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7067, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7082, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7087, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7092, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7097, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7102, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7107, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7112, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7118, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7123, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7128, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7133, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7138, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7143, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7148, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7153, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7158, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 3
    ####################################################################
    @classmethod
    def get_caller_info_c1s(cls,
                            exp_stack: Deque[CallerInfo],
                            capsys: Optional[Any]) -> None:
        """Get caller info class method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1S',
                                     func_name='get_caller_info_c1s',
                                     line_num=5402)
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
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7215, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7220, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7225, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7230, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7235, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7240, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7245, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7251, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7256, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7261, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7266, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7271, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7276, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7281, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7286, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7291, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 4
    ####################################################################
    def get_caller_info_m1bo(self,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1S',
                                     func_name='get_caller_info_m1bo',
                                     line_num=5533)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7318, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7325, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7332, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7347, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7352, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7357, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7362, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7367, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7372, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7377, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7383, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7388, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7393, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7398, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7403, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7408, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7413, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7418, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7423, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 5
    ####################################################################
    @staticmethod
    def get_caller_info_s1bo(exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded static method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1S',
                                     func_name='get_caller_info_s1bo',
                                     line_num=5664)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7450, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7457, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7464, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7479, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7484, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7489, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7494, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7499, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7504, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7509, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7515, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7520, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7525, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7530, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7535, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7540, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7545, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7550, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7555, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 6
    ####################################################################
    @classmethod
    def get_caller_info_c1bo(cls,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded class method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1S',
                                     func_name='get_caller_info_c1bo',
                                     line_num=5796)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7583, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7590, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7597, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7612, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7617, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7622, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7627, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7632, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7637, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7642, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7648, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7653, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7658, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7663, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7668, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7673, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7678, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7683, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7688, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 7
    ####################################################################
    def get_caller_info_m1sb(self,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1S',
                                     func_name='get_caller_info_m1sb',
                                     line_num=5927)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7715, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7722, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7729, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call base class normal method target
        update_stack(exp_stack=exp_stack, line_num=7744, add=0)
        self.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=7747, add=1)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7751, add=1)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7756, add=0)
        self.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7758, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7760, add=1)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7763, add=1)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7768, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7770, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7773, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7778, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7783, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7788, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7793, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7798, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7803, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7808, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7814, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7819, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7824, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7829, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7834, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7839, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7844, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7849, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7854, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s1sb(exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded static method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1S',
                                     func_name='get_caller_info_s1sb',
                                     line_num=6092)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=7881, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7888, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7895, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call base class normal method target
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=7911, add=1)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7915, add=1)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7920, add=1)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7923, add=1)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7928, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7931, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7936, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7941, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7946, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7951, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7956, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7961, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7966, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7972, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7977, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7982, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7987, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7992, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7997, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8002, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8007, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8012, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 1S Method 9
    ####################################################################
    @classmethod
    def get_caller_info_c1sb(cls,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded class method 1.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo1S',
                                     func_name='get_caller_info_c1sb',
                                     line_num=6250)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8040, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8047, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8054, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call base class normal method target
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=8070, add=1)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=8074, add=1)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=8079, add=1)
        cls.get_caller_info_s1bt(exp_stack=exp_stack,
                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8082, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8084, add=1)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8087, add=1)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=8092, add=0)
        cls.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8094, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8096, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8099, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8104, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=8109, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8114, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8119, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8124, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8129, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8134, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=8140, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8145, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8150, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8155, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8160, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8165, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8170, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8175, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8180, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

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
    def get_caller_info_m2(self,
                           exp_stack: Deque[CallerInfo],
                           capsys: Optional[Any]) -> None:
        """Get caller info method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        self.var1 += 1
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2',
                                     func_name='get_caller_info_m2',
                                     line_num=6428)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8219, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8226, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8233, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8248, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8253, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8258, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8263, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8268, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8273, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8278, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8284, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8289, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8294, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8299, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8304, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8309, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8314, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8319, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8324, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 2
    ####################################################################
    @staticmethod
    def get_caller_info_s2(exp_stack: Deque[CallerInfo],
                           capsys: Optional[Any]) -> None:
        """Get caller info static method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2',
                                     func_name='get_caller_info_s2',
                                     line_num=6559)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8351, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8358, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8365, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8380, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8385, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8390, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8395, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8400, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8405, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8410, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8416, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8421, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8426, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8431, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8436, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8441, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8446, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8451, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8456, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 3
    ####################################################################
    @classmethod
    def get_caller_info_c2(cls,
                           exp_stack: Deque[CallerInfo],
                           capsys: Optional[Any]) -> None:
        """Get caller info class method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output
        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2',
                                     func_name='get_caller_info_c2',
                                     line_num=6690)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8483, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8490, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8497, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8512, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8517, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8522, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8527, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8532, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8537, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8542, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8548, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8553, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8558, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8563, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8568, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8573, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8578, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8583, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8588, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 4
    ####################################################################
    def get_caller_info_m2bo(self,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2',
                                     func_name='get_caller_info_m2bo',
                                     line_num=6821)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8615, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8622, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8629, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8644, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8649, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8654, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8659, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8664, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8669, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8674, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8680, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8685, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8690, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8695, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8700, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8705, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8710, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8715, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8720, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 5
    ####################################################################
    @staticmethod
    def get_caller_info_s2bo(exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded static method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2',
                                     func_name='get_caller_info_s2bo',
                                     line_num=6952)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8747, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8754, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8761, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8776, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8781, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8786, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8791, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8796, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8801, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8806, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8812, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8817, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8822, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8827, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8832, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8837, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8842, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8847, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8852, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 6
    ####################################################################
    @classmethod
    def get_caller_info_c2bo(cls,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded class method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2',
                                     func_name='get_caller_info_c2bo',
                                     line_num=7084)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=8880, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8887, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8894, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8909, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8914, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8919, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8924, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8929, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8934, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8939, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8945, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8950, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8955, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8960, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8965, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8970, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8975, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8980, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8985, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 7
    ####################################################################
    def get_caller_info_m2bt(self,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        self.var1 += 1
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2',
                                     func_name='get_caller_info_m2bt',
                                     line_num=7216)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9013, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9020, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9027, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9042, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9047, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9052, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9057, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9062, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9067, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9072, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9078, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9083, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9088, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9093, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9098, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9103, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9108, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9113, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9118, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s2bt(exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded static method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2',
                                     func_name='get_caller_info_s2bt',
                                     line_num=7347)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9145, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9152, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9159, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9174, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9179, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9184, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9189, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9194, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9199, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9204, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9210, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9215, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9220, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9225, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9230, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9235, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9240, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9245, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9250, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2 Method 9
    ####################################################################
    @classmethod
    def get_caller_info_c2bt(cls,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded class method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2',
                                     func_name='get_caller_info_c2bt',
                                     line_num=7479)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9278, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9285, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9292, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9307, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9312, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9317, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9322, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9327, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9332, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9337, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9343, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9348, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9353, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9358, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9363, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9368, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9373, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9378, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9383, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

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
    def get_caller_info_m2s(self,
                            exp_stack: Deque[CallerInfo],
                            capsys: Optional[Any]) -> None:
        """Get caller info method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output
        """
        self.var1 += 1
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2S',
                                     func_name='get_caller_info_m2s',
                                     line_num=7622)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9422, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9429, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9436, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9451, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9456, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9461, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9466, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9471, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9476, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9481, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9487, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9492, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9497, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9502, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9507, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9512, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9517, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9522, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9527, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 2
    ####################################################################
    @staticmethod
    def get_caller_info_s2s(exp_stack: Deque[CallerInfo],
                            capsys: Optional[Any]) -> None:
        """Get caller info static method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2S',
                                     func_name='get_caller_info_s2s',
                                     line_num=7753)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9554, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9561, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9568, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9583, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9588, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9593, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9598, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9603, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9608, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9613, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9619, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9624, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9629, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9634, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9639, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9644, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9649, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9654, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9659, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 3
    ####################################################################
    @classmethod
    def get_caller_info_c2s(cls,
                            exp_stack: Deque[CallerInfo],
                            capsys: Optional[Any]) -> None:
        """Get caller info class method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2S',
                                     func_name='get_caller_info_c2s',
                                     line_num=7885)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9687, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9694, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9701, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9716, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9721, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9726, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9731, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9736, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9741, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9746, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9752, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9757, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9762, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9767, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9772, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9777, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9782, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9787, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9792, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 4
    ####################################################################
    def get_caller_info_m2bo(self,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2S',
                                     func_name='get_caller_info_m2bo',
                                     line_num=8016)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9819, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9826, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9833, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9848, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9853, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9858, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9863, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9868, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9873, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9878, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9884, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9889, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9894, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9899, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9904, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9909, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9914, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9919, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9924, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 5
    ####################################################################
    @staticmethod
    def get_caller_info_s2bo(exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded static method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2S',
                                     func_name='get_caller_info_s2bo',
                                     line_num=8147)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=9951, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9958, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9965, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=9980, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9985, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9990, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9995, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10000, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10005, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10010, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10016, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10021, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10026, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10031, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10036, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10041, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10046, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10051, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10056, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 6
    ####################################################################
    @classmethod
    def get_caller_info_c2bo(cls,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded class method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2S',
                                     func_name='get_caller_info_c2bo',
                                     line_num=8279)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10084, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10091, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10098, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10113, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10118, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10123, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10128, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10133, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10138, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10143, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10149, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10154, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10159, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10164, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10169, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10174, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10179, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10184, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10189, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 7
    ####################################################################
    def get_caller_info_m2sb(self,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2S',
                                     func_name='get_caller_info_m2sb',
                                     line_num=8410)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10216, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10223, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10230, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call base class normal method target
        update_stack(exp_stack=exp_stack, line_num=10245, add=0)
        self.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=10248, add=1)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10252, add=1)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10257, add=0)
        self.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10259, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10261, add=1)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10264, add=1)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10269, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10271, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10274, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10279, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10284, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10289, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10294, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10299, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10304, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10309, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10315, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10320, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10325, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10330, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10335, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10340, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10345, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10350, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10355, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s2sb(exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded static method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2S',
                                     func_name='get_caller_info_s2sb',
                                     line_num=8575)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10382, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10389, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10396, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call base class normal method target
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=10412, add=1)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10416, add=1)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10421, add=1)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10424, add=1)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10429, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10432, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10437, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10442, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10447, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10452, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10457, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10462, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10467, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10473, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10478, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10483, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10488, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10493, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10498, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10503, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10508, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10513, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 2S Method 9
    ####################################################################
    @classmethod
    def get_caller_info_c2sb(cls,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded class method 2.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo2S',
                                     func_name='get_caller_info_c2sb',
                                     line_num=8733)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10541, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10548, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10555, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call base class normal method target
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=10571, add=1)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10575, add=1)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10580, add=1)
        cls.get_caller_info_s2bt(exp_stack=exp_stack,
                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10583, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10585, add=1)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10588, add=1)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10593, add=0)
        cls.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10595, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10597, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10600, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10605, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10610, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10615, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10620, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10625, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10630, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10635, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10641, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10646, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10651, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10656, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10661, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10666, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10671, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10676, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10681, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

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
    def get_caller_info_m3(self,
                           exp_stack: Deque[CallerInfo],
                           capsys: Optional[Any]) -> None:
        """Get caller info method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        self.var1 += 1
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3',
                                     func_name='get_caller_info_m3',
                                     line_num=8911)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10720, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10727, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10734, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 2
    ####################################################################
    @staticmethod
    def get_caller_info_s3(exp_stack: Deque[CallerInfo],
                           capsys: Optional[Any]) -> None:
        """Get caller info static method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3',
                                     func_name='get_caller_info_s3',
                                     line_num=8961)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10771, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10778, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10785, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 3
    ####################################################################
    @classmethod
    def get_caller_info_c3(cls,
                           exp_stack: Deque[CallerInfo],
                           capsys: Optional[Any]) -> None:
        """Get caller info class method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output
        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3',
                                     func_name='get_caller_info_c3',
                                     line_num=9011)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10822, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10829, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10836, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 4
    ####################################################################
    def get_caller_info_m3bo(self,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3',
                                     func_name='get_caller_info_m3bo',
                                     line_num=9061)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10873, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10880, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10887, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 5
    ####################################################################
    @staticmethod
    def get_caller_info_s3bo(exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded static method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3',
                                     func_name='get_caller_info_s3bo',
                                     line_num=9111)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10924, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10931, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10938, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 6
    ####################################################################
    @classmethod
    def get_caller_info_c3bo(cls,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded class method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3',
                                     func_name='get_caller_info_c3bo',
                                     line_num=9162)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=10976, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10983, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10990, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 7
    ####################################################################
    def get_caller_info_m3bt(self,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        self.var1 += 1
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3',
                                     func_name='get_caller_info_m3bt',
                                     line_num=9213)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11028, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11035, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11042, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s3bt(exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded static method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3',
                                     func_name='get_caller_info_s3bt',
                                     line_num=9263)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11079, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11086, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11093, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3 Method 9
    ####################################################################
    @classmethod
    def get_caller_info_c3bt(cls,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded class method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3',
                                     func_name='get_caller_info_c3bt',
                                     line_num=9314)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11131, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11138, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11145, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

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
    def get_caller_info_m3s(self,
                            exp_stack: Deque[CallerInfo],
                            capsys: Optional[Any]) -> None:
        """Get caller info method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output
        """
        self.var1 += 1
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3S',
                                     func_name='get_caller_info_m3s',
                                     line_num=9376)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11194, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11201, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11208, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 2
    ####################################################################
    @staticmethod
    def get_caller_info_s3s(exp_stack: Deque[CallerInfo],
                            capsys: Optional[Any]) -> None:
        """Get caller info static method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3S',
                                     func_name='get_caller_info_s3s',
                                     line_num=9426)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11245, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11252, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11259, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 3
    ####################################################################
    @classmethod
    def get_caller_info_c3s(cls,
                            exp_stack: Deque[CallerInfo],
                            capsys: Optional[Any]) -> None:
        """Get caller info class method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3S',
                                     func_name='get_caller_info_c3s',
                                     line_num=9477)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11297, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11304, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11311, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 4
    ####################################################################
    def get_caller_info_m3bo(self,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3S',
                                     func_name='get_caller_info_m3bo',
                                     line_num=9527)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11348, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11355, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11362, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 5
    ####################################################################
    @staticmethod
    def get_caller_info_s3bo(exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded static method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3S',
                                     func_name='get_caller_info_s3bo',
                                     line_num=9577)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11399, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11406, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11413, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 6
    ####################################################################
    @classmethod
    def get_caller_info_c3bo(cls,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded class method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3S',
                                     func_name='get_caller_info_c3bo',
                                     line_num=9628)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11451, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11458, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11465, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 7
    ####################################################################
    def get_caller_info_m3sb(self,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3S',
                                     func_name='get_caller_info_m3sb',
                                     line_num=9678)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11502, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11509, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11516, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call base class normal method target
        update_stack(exp_stack=exp_stack, line_num=11531, add=0)
        self.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=11534, add=1)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11538, add=1)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11543, add=0)
        self.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11545, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11547, add=1)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11550, add=1)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11555, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11557, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11560, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 8
    ####################################################################
    @staticmethod
    def get_caller_info_s3sb(exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded static method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3S',
                                     func_name='get_caller_info_s3sb',
                                     line_num=9762)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11587, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11594, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11601, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call base class normal method target
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=11617, add=1)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11621, add=1)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11626, add=1)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11629, add=1)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11634, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11637, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ####################################################################
    # Class 3S Method 9
    ####################################################################
    @classmethod
    def get_caller_info_c3sb(cls,
                             exp_stack: Deque[CallerInfo],
                             capsys: Optional[Any]) -> None:
        """Get caller info overloaded class method 3.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='ClassGetCallerInfo3S',
                                     func_name='get_caller_info_c3sb',
                                     line_num=9839)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=11665, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11672, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11679, add=0)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            diag_msg_args = TestDiagMsg.get_diag_msg_args(
                depth_arg=len(exp_stack),
                msg_arg=['message 1', 1])

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys,
                            diag_msg_args=diag_msg_args)

        # call base class normal method target
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=11695, add=1)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11699, add=1)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11704, add=1)
        cls.get_caller_info_s3bt(exp_stack=exp_stack,
                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11707, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11709, add=1)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11712, add=1)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11717, add=0)
        cls.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11719, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11721, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11724, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


########################################################################
# following tests needs to be at module level (i.e., script form)
########################################################################

########################################################################
# test get_caller_info from module (script) level
########################################################################
exp_stack0: Deque[CallerInfo] = deque()
exp_caller_info0 = CallerInfo(mod_name='test_diag_msg.py',
                              cls_name='',
                              func_name='',
                              line_num=9921)

exp_stack0.append(exp_caller_info0)
update_stack(exp_stack=exp_stack0, line_num=11748, add=0)
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
update_stack(exp_stack=exp_stack0, line_num=11757, add=0)
call_seq0 = get_formatted_call_sequence(depth=1)

assert call_seq0 == get_exp_seq(exp_stack=exp_stack0)

########################################################################
# test diag_msg from module (script) level
# note that this is just a smoke test and is only visually verified
########################################################################
diag_msg()  # basic, empty msg
diag_msg('hello')
diag_msg(depth=2)
diag_msg('hello2', depth=3)
diag_msg(depth=4, end='\n\n')
diag_msg('hello3', depth=5, end='\n\n')

# call module level function
update_stack(exp_stack=exp_stack0, line_num=11774, add=0)
func_get_caller_info_1(exp_stack=exp_stack0, capsys=None)

# call method
cls_get_caller_info01 = ClassGetCallerInfo1()
update_stack(exp_stack=exp_stack0, line_num=11779, add=0)
cls_get_caller_info01.get_caller_info_m1(exp_stack=exp_stack0, capsys=None)

# call static method
update_stack(exp_stack=exp_stack0, line_num=11783, add=0)
cls_get_caller_info01.get_caller_info_s1(exp_stack=exp_stack0, capsys=None)

# call class method
update_stack(exp_stack=exp_stack0, line_num=11787, add=0)
ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack0, capsys=None)

# call overloaded base class method
update_stack(exp_stack=exp_stack0, line_num=11791, add=0)
cls_get_caller_info01.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class static method
update_stack(exp_stack=exp_stack0, line_num=11795, add=0)
cls_get_caller_info01.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class class method
update_stack(exp_stack=exp_stack0, line_num=11799, add=0)
ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call subclass method
cls_get_caller_info01S = ClassGetCallerInfo1S()
update_stack(exp_stack=exp_stack0, line_num=11804, add=0)
cls_get_caller_info01S.get_caller_info_m1s(exp_stack=exp_stack0, capsys=None)

# call subclass static method
update_stack(exp_stack=exp_stack0, line_num=11808, add=0)
cls_get_caller_info01S.get_caller_info_s1s(exp_stack=exp_stack0, capsys=None)

# call subclass class method
update_stack(exp_stack=exp_stack0, line_num=11812, add=0)
ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass method
update_stack(exp_stack=exp_stack0, line_num=11816, add=0)
cls_get_caller_info01S.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass static method
update_stack(exp_stack=exp_stack0, line_num=11820, add=0)
cls_get_caller_info01S.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass class method
update_stack(exp_stack=exp_stack0, line_num=11824, add=0)
ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call base method from subclass method
update_stack(exp_stack=exp_stack0, line_num=11828, add=0)
cls_get_caller_info01S.get_caller_info_m1sb(exp_stack=exp_stack0, capsys=None)

# call base static method from subclass static method
update_stack(exp_stack=exp_stack0, line_num=11832, add=0)
cls_get_caller_info01S.get_caller_info_s1sb(exp_stack=exp_stack0, capsys=None)

# call base class method from subclass class method
update_stack(exp_stack=exp_stack0, line_num=11836, add=0)
ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack0, capsys=None)
