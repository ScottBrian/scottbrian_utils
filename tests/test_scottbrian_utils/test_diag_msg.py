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

###############################################################################
# MyPy experiments
###############################################################################
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


###############################################################################
# DiagMsgArgs NamedTuple
###############################################################################
class DiagMsgArgs(NamedTuple):
    """Structure for the testing of various args for diag_msg."""
    arg_bits: int
    dt_format_arg: str
    depth_arg: int
    msg_arg: List[Union[str, int]]
    file_arg: str


###############################################################################
# depth_arg fixture
###############################################################################
depth_arg_list = [None, 0, 1, 2, 3]


@pytest.fixture(params=depth_arg_list)  # type: ignore
def depth_arg(request: Any) -> int:
    """Using different depth args.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# file_arg fixture
###############################################################################
file_arg_list = [None, 'sys.stdout', 'sys.stderr']


@pytest.fixture(params=file_arg_list)  # type: ignore
def file_arg(request: Any) -> str:
    """Using different file arg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(str, request.param)


###############################################################################
# latest_arg fixture
###############################################################################
latest_arg_list = [None, 0, 1, 2, 3]


@pytest.fixture(params=latest_arg_list)  # type: ignore
def latest_arg(request: Any) -> Union[int, None]:
    """Using different depth args.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# msg_arg fixture
###############################################################################
msg_arg_list = [[None],
                ['one-word'],
                ['two words'],
                ['three + four'],
                ['two', 'items'],
                ['three', 'items', 'for you'],
                ['this', 'has', 'number', 4],
                ['here', 'some', 'math', 4 + 1]]


@pytest.fixture(params=msg_arg_list)  # type: ignore
def msg_arg(request: Any) -> List[str]:
    """Using different message arg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(List[str], request.param)


###############################################################################
# seq_slice is used to get a contiguous section of the sequence string
# which is needed to verify get_formatted_call_seq invocations where latest
# is non-zero or depth is beyond our known call sequence (i.e., the call seq
# string has system functions prior to calling the test case)
###############################################################################
def seq_slice(call_seq: str,
              start: int = 0,
              end: Optional[int] = None
              ) -> str:
    """Return a reduced depth call sequence string.

    Args:
        call_seq: The call sequence string to slice
        start: Species the latest entry to return with zero being most recent
        end: Specifies one entry earlier than the earliest entry to return

    Returns:
          A slice of the input call sequence string
    """
    seq_items = call_seq.split(' -> ')

    # Note that we allow start and end to both be zero, in which case an empty
    # sequence is returned. Also note that the sequence is earlier calls to
    # later calls from left to right, so a start of zero means the end of the
    # sequence (the right most entry) and the end is the depth, meaning how
    # far to go left toward earlier entries. The following code reverses the
    # meaning of start and end so that we can slice the sequence without
    # having to first reverse it.

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


###############################################################################
# get_exp_seq is a helper function used by many test cases
###############################################################################
def get_exp_seq(exp_stack: Deque[CallerInfo],
                latest: int = 0,
                depth: Optional[int] = None
                ) -> str:
    """Return the expected call sequence string based on the exp_stack.

    Args:
        exp_stack: The expected stack as modified by each test case
        depth: The number of entries to build
        latest: Specifies where to start in the seq for the most recent entry

    Returns:
          The call string that get_formatted_call_sequence is expected to
           return
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


###############################################################################
# verify_diag_msg is a helper function used by many test cases
###############################################################################
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
        diag_msg_args: Specifies the args used on the diag_msg invocation

    """
    # We are about to format the before and after times to match the precision
    # of the diag_msg time. In doing so, we may end up with the after time
    # appearing to be earlier than the before time if the times are very close
    # to 23:59:59 if the format does not include the date information (e.g.,
    # before_time ends up being 23:59:59.999938 and after_time end up being
    # 00:00:00.165). If this happens, we can't reliably check the diag_msg
    # time so we will simply skip the check. The following assert proves only
    # that the times passed in are good to start with before we strip off
    # any resolution.
    assert before_time < after_time

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
    if before_time <= after_time:  # if safe to proceed with low resolution
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


###############################################################################
# verify_call_seq is a helper function used by many test cases
###############################################################################
def verify_call_seq(exp_stack: Deque[CallerInfo],
                    call_seq: str,
                    seq_latest: Optional[int] = None,
                    seq_depth: Optional[int] = None) -> None:
    """Verify the captured msg is as expected.

    Args:
        exp_stack: The expected stack of callers
        call_seq: The call sequence from get_formatted_call_seq or from
                    diag_msg to check
        seq_latest: The value used for the get_formatted_call_seq latest arg
        seq_depth: The value used for the get_formatted_call_seq depth arg

    """
    # Note on call_seq_depth and exp_stack_depth: We need to test that
    # get_formatted_call_seq and diag_msg will correctly return the entries on
    # the real stack to the requested depth. The test cases involve calling
    # a sequence of functions so that we can grow the stack with known entries
    # and thus be able to verify them. The real stack will also have entries
    # for the system code prior to giving control to the first test case.
    # We need to be able to test the depth specification on the
    # get_formatted_call_seq and diag_msg, and this may cause the call
    # sequence to contain entries for the system. The call_seq_depth is used
    # to tell the verification code to limit the check to the entries we know
    # about and not the system entries. The exp_stack_depth is also needed
    # when we know we have limited the get_formatted_call_seq or diag_msg
    # in which case we can't use the entire exp_stack.
    # In the following table, the exp_stack depth is the number of functions
    # called, the get_formatted_call_seq latest and depth are the values
    # specified for the get_formatted_call_sequence latest and depth args.
    # The seq_slice latest and depth are the values to use for the slice
    # (remembering that the call_seq passed to verify_call_seq may already
    # be a slice of the real stack). Note that values of 0 and None for latest
    # and depth, respectively, mean slicing in not needed. The get_exp_seq
    # latest and and depth specify the slice of the exp_stack to use. Values
    # of 0 and None here mean no slicing is needed. Note also that from both
    # seq_slice and get_exp_seq, None for the depth arg means to return all of
    # the all remaining entries after any latest slicing is done. Also, a
    # value of no-test means that verify_call_seq can not do a verification
    # since the call_seq is not  in the range of the exp_stack.

    # exp_stk | get_formatted_call_seq | seq_slice         | get_exp_seq
    # depth   |           latest depth | start  |   end    | latest | depth
    # ------------------------------------------------------------------------
    #       1 |                0     1 |      0 | None (1) |      0 | None (1)
    #       1 |                0     2 |      0 |       1  |      0 | None (1)
    #       1 |                0     3 |      0 |       1  |      0 | None (1)
    #       1 |                1     1 |           no-test |     no-test
    #       1 |                1     2 |           no-test |     no-test
    #       1 |                1     3 |           no-test |     no-test
    #       1 |                2     1 |           no-test |     no-test
    #       1 |                2     2 |           no-test |     no-test
    #       1 |                2     3 |           no-test |     no-test
    #       2 |                0     1 |      0 | None (1) |      0 |       1
    #       2 |                0     2 |      0 | None (2) |      0 | None (2)
    #       2 |                0     3 |      0 |       2  |      0 | None (2)
    #       2 |                1     1 |      0 | None (1) |      1 | None (1)
    #       2 |                1     2 |      0 |       1  |      1 | None (1)
    #       2 |                1     3 |      0 |       1  |      1 | None (1)
    #       2 |                2     1 |           no-test |     no-test
    #       2 |                2     2 |           no-test |     no-test
    #       2 |                2     3 |           no-test |     no-test
    #       3 |                0     1 |      0 | None (1) |      0 |       1
    #       3 |                0     2 |      0 | None (2) |      0 |       2
    #       3 |                0     3 |      0 | None (3) |      0 | None (3)
    #       3 |                1     1 |      0 | None (1) |      1 |       1
    #       3 |                1     2 |      0 | None (2) |      1 | None (2)
    #       3 |                1     3 |      0 |       2  |      1 | None (2)
    #       3 |                2     1 |      0 | None (1) |      2 | None (1)
    #       3 |                2     2 |      0 |       1  |      2 | None (1)
    #       3 |                2     3 |      0 |       1  |      2 | None (1)

    # The following assert checks to make sure the call_seq obtained by the
    # get_formatted_call_seq has the correct number of entries and is
    # formatted correctly with arrows by calling seq_slice with the
    # get_formatted_call_seq seq_depth. In this case, the slice returned by
    # seq_slice should be exactly the same as the input
    if seq_depth is None:
        seq_depth = get_formatted_call_seq_depth

    assert call_seq == seq_slice(call_seq=call_seq, end=seq_depth)

    if seq_latest is None:
        seq_latest = 0

    if seq_latest < len(exp_stack):  # if we have enough stack entries to test
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


###############################################################################
# update stack with new line number
###############################################################################
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


###############################################################################
# Class to test get call sequence
###############################################################################
class TestCallSeq:
    """Class the test get_formatted_call_sequence."""
    ###########################################################################
    # Basic test for get_formatted_call_seq
    ###########################################################################
    def test_get_call_seq_basic(self) -> None:
        """Test basic get formatted call sequence function."""
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='test_get_call_seq_basic',
                                     line_num=420)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=457, add=0)
        call_seq = get_formatted_call_sequence()

        verify_call_seq(exp_stack=exp_stack, call_seq=call_seq)

    ###########################################################################
    # Test with latest and depth parms with stack of 1
    ###########################################################################
    def test_get_call_seq_with_parms(self,
                                     latest_arg: Optional[int] = None,
                                     depth_arg: Optional[int] = None
                                     ) -> None:
        """Test get_formatted_call_seq with parms at depth 1.

        Args:
            latest_arg: pytest fixture that specifies the how far back into the
                          stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to get

        """
        print('sys.version_info[0]:', sys.version_info[0])
        print('sys.version_info[1]:', sys.version_info[1])
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='test_get_call_seq_with_parms',
                                     line_num=449)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=487, add=0)
        call_seq = ''
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=490, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=493, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=496, add=1)
            call_seq = get_formatted_call_sequence(latest=latest_arg,
                                                   depth=depth_arg)
        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_latest=latest_arg,
                        seq_depth=depth_arg)

        update_stack(exp_stack=exp_stack, line_num=504, add=2)
        self.get_call_seq_depth_2(exp_stack=exp_stack,
                                  latest_arg=latest_arg,
                                  depth_arg=depth_arg)

    ###########################################################################
    # Test with latest and depth parms with stack of 2
    ###########################################################################
    def get_call_seq_depth_2(self,
                             exp_stack: Deque[CallerInfo],
                             latest_arg: Optional[int] = None,
                             depth_arg: Optional[int] = None
                             ) -> None:
        """Test get_formatted_call_seq at depth 2.

        Args:
            exp_stack: The expected stack of callers
            latest_arg: pytest fixture that specifies the how far back into the
                          stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to get

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='get_call_seq_depth_2',
                                     line_num=494)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=533, add=0)
        call_seq = ''
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=536, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=539, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=542, add=1)
            call_seq = get_formatted_call_sequence(latest=latest_arg,
                                                   depth=depth_arg)
        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_latest=latest_arg,
                        seq_depth=depth_arg)

        update_stack(exp_stack=exp_stack, line_num=550, add=2)
        self.get_call_seq_depth_3(exp_stack=exp_stack,
                                  latest_arg=latest_arg,
                                  depth_arg=depth_arg)

        exp_stack.pop()  # return with correct stack

    ###########################################################################
    # Test with latest and depth parms with stack of 3
    ###########################################################################
    def get_call_seq_depth_3(self,
                             exp_stack: Deque[CallerInfo],
                             latest_arg: Optional[int] = None,
                             depth_arg: Optional[int] = None
                             ) -> None:
        """Test get_formatted_call_seq at depth 3.

        Args:
            exp_stack: The expected stack of callers
            latest_arg: pytest fixture that specifies the how far back into the
                          stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to get

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='get_call_seq_depth_3',
                                     line_num=541)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=581, add=0)
        call_seq = ''
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=584, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=587, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=590, add=1)
            call_seq = get_formatted_call_sequence(latest=latest_arg,
                                                   depth=depth_arg)
        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_latest=latest_arg,
                        seq_depth=depth_arg)

        update_stack(exp_stack=exp_stack, line_num=598, add=2)
        self.get_call_seq_depth_4(exp_stack=exp_stack,
                                  latest_arg=latest_arg,
                                  depth_arg=depth_arg)

        exp_stack.pop()  # return with correct stack

    ###########################################################################
    # Test with latest and depth parms with stack of 4
    ###########################################################################
    def get_call_seq_depth_4(self,
                             exp_stack: Deque[CallerInfo],
                             latest_arg: Optional[int] = None,
                             depth_arg: Optional[int] = None
                             ) -> None:
        """Test get_formatted_call_seq at depth 4.

        Args:
            exp_stack: The expected stack of callers
            latest_arg: pytest fixture that specifies the how far back into the
                          stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to get

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='get_call_seq_depth_4',
                                     line_num=588)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=629, add=0)
        call_seq = ''
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=632, add=0)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=635, add=0)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=638, add=1)
            call_seq = get_formatted_call_sequence(latest=latest_arg,
                                                   depth=depth_arg)
        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_latest=latest_arg,
                        seq_depth=depth_arg)

        exp_stack.pop()  # return with correct stack

    ###########################################################################
    # Verify we can run off the end of the stack
    ###########################################################################
    def test_get_call_seq_full_stack(self) -> None:
        """Test to ensure we can run the entire stack."""
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='test_get_call_seq_full_stack',
                                     line_num=620)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=662, add=1)
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


###############################################################################
# TestDiagMsg class
###############################################################################
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

    ###########################################################################
    # Get the arg specifications for diag_msg
    ###########################################################################
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

    ###########################################################################
    # Basic diag_msg test
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=773, add=0)
        before_time = datetime.now()
        diag_msg()
        after_time = datetime.now()

        diag_msg_args = self.get_diag_msg_args()
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        diag_msg_args=diag_msg_args)

    ###########################################################################
    # diag_msg with parms
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=815, add=0)
        diag_msg_args = self.get_diag_msg_args(dt_format_arg=dt_format_arg,
                                               depth_arg=depth_arg,
                                               msg_arg=msg_arg,
                                               file_arg=file_arg)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=818, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=821, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=824, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=828, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=831, add=1)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=835, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=839, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=844, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=847, add=1)
            diag_msg(dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=851, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=855, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=860, add=1)
            diag_msg(depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=864, add=2)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg),
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=869, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=874, add=3)
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

        update_stack(exp_stack=exp_stack, line_num=888, add=2)
        self.diag_msg_depth_2(exp_stack=exp_stack,
                              capsys=capsys,
                              diag_msg_args=diag_msg_args)

    ###########################################################################
    # Depth 2 test
    ###########################################################################
    def diag_msg_depth_2(self,
                         exp_stack: Deque[CallerInfo],
                         capsys: pytest.CaptureFixture[str],
                         diag_msg_args: DiagMsgArgs) -> None:
        """Test msg_diag with two callers in the sequence.

        Args:
            exp_stack: The expected stack as modified by each test case
            capsys: pytest fixture that captures output
            diag_msg_args: Specifies the args to use on the diag_msg invocation

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestDiagMsg',
                                     func_name='diag_msg_depth_2',
                                     line_num=867)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=915, add=0)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=918, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=921, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=924, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=928, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=931, add=1)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=935, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=939, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=944, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=947, add=1)
            diag_msg(dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=951, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=955, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=960, add=1)
            diag_msg(depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=964, add=2)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg),
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=969, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=974, add=3)
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

        update_stack(exp_stack=exp_stack, line_num=988, add=2)
        self.diag_msg_depth_3(exp_stack=exp_stack,
                              capsys=capsys,
                              diag_msg_args=diag_msg_args)

        exp_stack.pop()  # return with correct stack

    ###########################################################################
    # Depth 3 test
    ###########################################################################
    def diag_msg_depth_3(self,
                         exp_stack: Deque[CallerInfo],
                         capsys: pytest.CaptureFixture[str],
                         diag_msg_args: DiagMsgArgs) -> None:
        """Test msg_diag with three callers in the sequence.

        Args:
            exp_stack: The expected stack as modified by each test case
            capsys: pytest fixture that captures output
            diag_msg_args: Specifies the args to use on the diag_msg invocation

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestDiagMsg',
                                     func_name='diag_msg_depth_3',
                                     line_num=968)
        exp_stack.append(exp_caller_info)
        update_stack(exp_stack=exp_stack, line_num=1017, add=0)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1020, add=0)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1023, add=0)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1026, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1030, add=0)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1033, add=1)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1037, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1041, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1046, add=0)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1049, add=1)
            diag_msg(dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1053, add=1)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1057, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1062, add=1)
            diag_msg(depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1066, add=2)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg),
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1071, add=2)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1076, add=3)
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


###############################################################################
# The functions and classes below handle various combinations of cases where
# one function calls another up to a level of 5 functions deep. The first
# caller can be at the module level (i.e., script level), or a module
# function, class method, static method, or class method. The second and
# subsequent callers can be any but the module level caller. The following
# grouping shows the possibilities:
# {mod, func, method, static_method, cls_method}
#       -> {func, method, static_method, cls_method}
#
###############################################################################
# func 0
###############################################################################
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
    update_stack(exp_stack=exp_stack, line_num=1121, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=1128, add=0)
    call_seq = get_formatted_call_sequence(depth=1)

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    update_stack(exp_stack=exp_stack, line_num=1135, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=1148, add=0)
    func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info1 = ClassGetCallerInfo1()
    update_stack(exp_stack=exp_stack, line_num=1153, add=0)
    cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=1157, add=0)
    cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=1161, add=0)
    ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=1165, add=1)
    cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=1170, add=1)
    cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=1175, add=1)
    ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info1s = ClassGetCallerInfo1S()
    update_stack(exp_stack=exp_stack, line_num=1181, add=1)
    cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=1186, add=1)
    cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=1191, add=1)
    ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=1196, add=1)
    cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=1201, add=1)
    cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=1206, add=1)
    ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=1211, add=1)
    cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=1216, add=1)
    cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=1221, add=1)
    ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                              capsys=capsys)

    ###########################################################################
    # Inner class defined inside function test_func_get_caller_info_0
    ###########################################################################
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
            update_stack(exp_stack=exp_stack_g, line_num=1251, add=0)
            for i_g, expected_caller_info_g in enumerate(
                    list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1258, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1266, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1280, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1285, add=1)
            cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1290, add=1)
            cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1295, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack_g,
                                                   capsys=capsys_g)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1300, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1305, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1310, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1316, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1321, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1326, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1331, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1336, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1341, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1346, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1351, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1356, add=1)
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
            update_stack(exp_stack=exp_stack_g, line_num=1381, add=0)
            for i_g, expected_caller_info_g in enumerate(
                    list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1388, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1396, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1410, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1415, add=1)
            cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1420, add=1)
            cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1425, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack_g,
                                                   capsys=capsys_g)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1430, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1435, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1440, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1446, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1451, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1456, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1461, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1466, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1471, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1476, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1481, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1486, add=1)
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
            update_stack(exp_stack=exp_stack_g, line_num=1512, add=0)
            for i_g, expected_caller_info_g in enumerate(
                    list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=1519, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=1527, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=1541, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_g, line_num=1546, add=1)
            cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=1551, add=1)
            cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=1556, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack_g,
                                                   capsys=capsys_g)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=1561, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=1566, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=1571, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_g, line_num=1577, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1582, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1587, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1592, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1597, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1602, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=1607, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=1612, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=1617, add=1)
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
            update_stack(exp_stack=exp_stack_h, line_num=1648, add=0)
            for i_h, expected_caller_info_h in enumerate(
                    list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=1655, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=1663, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=1677, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=1682, add=1)
            cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=1687, add=1)
            cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=1692, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack_h,
                                                   capsys=capsys_h)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=1697, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=1702, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=1707, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=1713, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1718, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1723, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1728, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1733, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1738, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1743, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1748, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1753, add=1)
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
            update_stack(exp_stack=exp_stack_h, line_num=1778, add=0)
            for i_h, expected_caller_info_h in enumerate(
                    list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=1785, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=1793, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=1807, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=1812, add=1)
            cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=1817, add=1)
            cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=1822, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack_h,
                                                   capsys=capsys_h)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=1827, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=1832, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=1837, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=1843, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1848, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1853, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1858, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1863, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1868, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1873, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1878, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1883, add=1)
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
            update_stack(exp_stack=exp_stack_h, line_num=1909, add=0)
            for i_h, expected_caller_info_h in enumerate(
                    list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=1916, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=1924, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=1938, add=0)
            func_get_caller_info_1(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info1 = ClassGetCallerInfo1()
            update_stack(exp_stack=exp_stack_h, line_num=1943, add=1)
            cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=1948, add=1)
            cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=1953, add=1)
            ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack_h,
                                                   capsys=capsys_h)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=1958, add=1)
            cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=1963, add=1)
            cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=1968, add=1)
            ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call subclass method
            cls_get_caller_info1s = ClassGetCallerInfo1S()
            update_stack(exp_stack=exp_stack_h, line_num=1974, add=1)
            cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1979, add=1)
            cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1984, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=1989, add=1)
            cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=1994, add=1)
            cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=1999, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2004, add=1)
            cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2009, add=1)
            cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2014, add=1)
            ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            exp_stack.pop()

    a_inner = Inner()
    # call Inner method
    update_stack(exp_stack=exp_stack, line_num=2022, add=0)
    a_inner.g1(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2025, add=0)
    a_inner.g2_static(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2028, add=0)
    a_inner.g3_class(exp_stack_g=exp_stack, capsys_g=capsys)

    a_inherit = Inherit()

    update_stack(exp_stack=exp_stack, line_num=2033, add=0)
    a_inherit.h1(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2036, add=0)
    a_inherit.h2_static(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2039, add=0)
    a_inherit.h3_class(exp_stack_h=exp_stack, capsys_h=capsys)

    exp_stack.pop()


###############################################################################
# func 1
###############################################################################
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
    update_stack(exp_stack=exp_stack, line_num=2065, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=2072, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=2080, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=2093, add=0)
    func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info2 = ClassGetCallerInfo2()
    update_stack(exp_stack=exp_stack, line_num=2098, add=0)
    cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=2102, add=0)
    cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=2106, add=0)
    ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=2110, add=1)
    cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=2115, add=1)
    cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=2120, add=1)
    ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info2s = ClassGetCallerInfo2S()
    update_stack(exp_stack=exp_stack, line_num=2126, add=1)
    cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=2131, add=1)
    cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=2136, add=1)
    ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=2141, add=1)
    cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=2146, add=1)
    cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=2151, add=1)
    ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=2156, add=1)
    cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=2161, add=1)
    cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=2166, add=1)
    ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                              capsys=capsys)

    ###########################################################################
    # Inner class defined inside function test_func_get_caller_info_0
    ###########################################################################
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
            update_stack(exp_stack=exp_stack_g, line_num=2196, add=0)
            for i_g, expected_caller_info_g in enumerate(
                    list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2203, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2211, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2225, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2230, add=1)
            cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2235, add=1)
            cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2240, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack_g,
                                                   capsys=capsys_g)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2245, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2250, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2255, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2261, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2266, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2271, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2276, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2281, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2286, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2291, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2296, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2301, add=1)
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
            update_stack(exp_stack=exp_stack_g, line_num=2326, add=0)
            for i_g, expected_caller_info_g in enumerate(
                    list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2333, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2341, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2355, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2360, add=1)
            cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2365, add=1)
            cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2370, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack_g,
                                                   capsys=capsys_g)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2375, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2380, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2385, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2391, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2396, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2401, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2406, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2411, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2416, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2421, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2426, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2431, add=1)
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
            update_stack(exp_stack=exp_stack_g, line_num=2457, add=0)
            for i_g, expected_caller_info_g in enumerate(
                    list(reversed(exp_stack_g))):
                try:
                    frame_g = _getframe(i_g)
                    caller_info_g = get_caller_info(frame_g)
                finally:
                    del frame_g
                assert caller_info_g == expected_caller_info_g

            # test call sequence
            update_stack(exp_stack=exp_stack_g, line_num=2464, add=0)
            call_seq_g = get_formatted_call_sequence(depth=len(exp_stack_g))

            assert call_seq_g == get_exp_seq(exp_stack=exp_stack_g)

            # test diag_msg
            if capsys_g:  # if capsys_g, test diag_msg
                update_stack(exp_stack=exp_stack_g, line_num=2472, add=0)
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
            update_stack(exp_stack=exp_stack_g, line_num=2486, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_g, capsys=capsys_g)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_g, line_num=2491, add=1)
            cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call static method
            update_stack(exp_stack=exp_stack_g, line_num=2496, add=1)
            cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack_g,
                                                    capsys=capsys_g)

            # call class method
            update_stack(exp_stack=exp_stack_g, line_num=2501, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack_g,
                                                   capsys=capsys_g)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_g, line_num=2506, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_g, line_num=2511, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_g, line_num=2516, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_g, line_num=2522, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2527, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2532, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack_g,
                                                     capsys=capsys_g)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2537, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2542, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2547, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack_g,
                                                      capsys=capsys_g)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_g, line_num=2552, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_g, line_num=2557, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack_g,
                                                       capsys=capsys_g)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_g, line_num=2562, add=1)
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
            update_stack(exp_stack=exp_stack_h, line_num=2593, add=0)
            for i_h, expected_caller_info_h in enumerate(
                    list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2600, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2608, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2622, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2627, add=1)
            cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2632, add=1)
            cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2637, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack_h,
                                                   capsys=capsys_h)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2642, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2647, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2652, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=2658, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2663, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2668, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2673, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2678, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2683, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2688, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2693, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2698, add=1)
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
            update_stack(exp_stack=exp_stack_h, line_num=2723, add=0)
            for i_h, expected_caller_info_h in enumerate(
                    list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2730, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2738, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2752, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2757, add=1)
            cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2762, add=1)
            cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2767, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack_h,
                                                   capsys=capsys_h)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2772, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2777, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2782, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=2788, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2793, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2798, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2803, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2808, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2813, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2818, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2823, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2828, add=1)
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
            update_stack(exp_stack=exp_stack_h, line_num=2854, add=0)
            for i_h, expected_caller_info_h in enumerate(
                    list(reversed(exp_stack_h))):
                try:
                    frame_h = _getframe(i_h)
                    caller_info_h = get_caller_info(frame_h)
                finally:
                    del frame_h
                assert caller_info_h == expected_caller_info_h

            # test call sequence
            update_stack(exp_stack=exp_stack_h, line_num=2861, add=0)
            call_seq_h = get_formatted_call_sequence(depth=len(exp_stack_h))

            assert call_seq_h == get_exp_seq(exp_stack=exp_stack_h)

            # test diag_msg
            if capsys_h:  # if capsys_h, test diag_msg
                update_stack(exp_stack=exp_stack_h, line_num=2869, add=0)
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
            update_stack(exp_stack=exp_stack_h, line_num=2883, add=0)
            func_get_caller_info_2(exp_stack=exp_stack_h, capsys=capsys_h)

            # call method
            cls_get_caller_info2 = ClassGetCallerInfo2()
            update_stack(exp_stack=exp_stack_h, line_num=2888, add=1)
            cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call static method
            update_stack(exp_stack=exp_stack_h, line_num=2893, add=1)
            cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack_h,
                                                    capsys=capsys_h)

            # call class method
            update_stack(exp_stack=exp_stack_h, line_num=2898, add=1)
            ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack_h,
                                                   capsys=capsys_h)

            # call overloaded base class method
            update_stack(exp_stack=exp_stack_h, line_num=2903, add=1)
            cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class static method
            update_stack(exp_stack=exp_stack_h, line_num=2908, add=1)
            cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call overloaded base class class method
            update_stack(exp_stack=exp_stack_h, line_num=2913, add=1)
            ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call subclass method
            cls_get_caller_info2s = ClassGetCallerInfo2S()
            update_stack(exp_stack=exp_stack_h, line_num=2919, add=1)
            cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2924, add=1)
            cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2929, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack_h,
                                                     capsys=capsys_h)

            # call overloaded subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2934, add=1)
            cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2939, add=1)
            cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call overloaded subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2944, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            # call base method from subclass method
            update_stack(exp_stack=exp_stack_h, line_num=2949, add=1)
            cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base static method from subclass static method
            update_stack(exp_stack=exp_stack_h, line_num=2954, add=1)
            cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack_h,
                                                       capsys=capsys_h)

            # call base class method from subclass class method
            update_stack(exp_stack=exp_stack_h, line_num=2959, add=1)
            ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack_h,
                                                      capsys=capsys_h)

            exp_stack.pop()

    a_inner = Inner()
    # call Inner method
    update_stack(exp_stack=exp_stack, line_num=2967, add=0)
    a_inner.g1(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2970, add=0)
    a_inner.g2_static(exp_stack_g=exp_stack, capsys_g=capsys)

    update_stack(exp_stack=exp_stack, line_num=2973, add=0)
    a_inner.g3_class(exp_stack_g=exp_stack, capsys_g=capsys)

    a_inherit = Inherit()

    update_stack(exp_stack=exp_stack, line_num=2978, add=0)
    a_inherit.h1(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2981, add=0)
    a_inherit.h2_static(exp_stack_h=exp_stack, capsys_h=capsys)

    update_stack(exp_stack=exp_stack, line_num=2984, add=0)
    a_inherit.h3_class(exp_stack_h=exp_stack, capsys_h=capsys)

    exp_stack.pop()


###############################################################################
# func 2
###############################################################################
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
    update_stack(exp_stack=exp_stack, line_num=3010, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=3017, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3025, add=0)
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
    update_stack(exp_stack=exp_stack, line_num=3038, add=0)
    func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info3 = ClassGetCallerInfo3()
    update_stack(exp_stack=exp_stack, line_num=3043, add=0)
    cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

    # call static method
    update_stack(exp_stack=exp_stack, line_num=3047, add=0)
    cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

    # call class method
    update_stack(exp_stack=exp_stack, line_num=3051, add=0)
    ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    update_stack(exp_stack=exp_stack, line_num=3055, add=1)
    cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    update_stack(exp_stack=exp_stack, line_num=3060, add=1)
    cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    update_stack(exp_stack=exp_stack, line_num=3065, add=1)
    ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info3s = ClassGetCallerInfo3S()
    update_stack(exp_stack=exp_stack, line_num=3071, add=1)
    cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    update_stack(exp_stack=exp_stack, line_num=3076, add=1)
    cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    update_stack(exp_stack=exp_stack, line_num=3081, add=1)
    ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    update_stack(exp_stack=exp_stack, line_num=3086, add=1)
    cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    update_stack(exp_stack=exp_stack, line_num=3091, add=1)
    cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    update_stack(exp_stack=exp_stack, line_num=3096, add=1)
    ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    update_stack(exp_stack=exp_stack, line_num=3101, add=1)
    cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    update_stack(exp_stack=exp_stack, line_num=3106, add=1)
    cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    update_stack(exp_stack=exp_stack, line_num=3111, add=1)
    ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                              capsys=capsys)

    exp_stack.pop()


###############################################################################
# func 3
###############################################################################
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
    update_stack(exp_stack=exp_stack, line_num=3138, add=0)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    update_stack(exp_stack=exp_stack, line_num=3145, add=0)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3153, add=0)
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


###############################################################################
# Classes
###############################################################################
###############################################################################
# Class 0
###############################################################################
class TestClassGetCallerInfo0:
    """Class to get caller info 0."""

    ###########################################################################
    # Class 0 Method 1
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=3197, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3204, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3211, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3224, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3229, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3234, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3239, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3244, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3249, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3254, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3260, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3265, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3270, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3275, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3280, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3285, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3290, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3295, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3300, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 2
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=3324, add=0)
        self.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3326, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0(exp_stack=exp_stack,
                                                   capsys=capsys)

        update_stack(exp_stack=exp_stack, line_num=3330, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=3332, add=1)
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
        update_stack(exp_stack=exp_stack, line_num=3354, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3361, add=0)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3368, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3381, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3386, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3391, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3396, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3401, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3406, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3411, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3417, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3422, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3427, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3432, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3437, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3442, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3447, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3452, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3457, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 3
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=3483, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3490, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3497, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3510, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3515, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3520, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3525, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3530, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3535, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3540, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3546, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3551, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3556, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3561, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3566, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3571, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3576, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3581, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3586, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 4
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=3612, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3619, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3626, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3639, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3644, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3649, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3654, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3659, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3664, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3669, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3675, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3680, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3685, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3690, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3695, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3700, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3705, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3710, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3715, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 5
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=3741, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3748, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3755, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3768, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3773, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3778, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3783, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3788, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3793, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3798, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3804, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3809, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3814, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3819, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3824, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3829, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3834, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3839, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3844, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 6
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=3871, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=3878, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=3885, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=3898, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=3903, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=3908, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=3913, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=3918, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=3923, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=3928, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=3934, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=3939, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=3944, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=3949, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=3954, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=3959, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=3964, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=3969, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=3974, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 7
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=4000, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4007, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4014, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4027, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4032, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4037, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4042, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4047, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4052, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4057, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4063, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4068, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4073, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4078, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4083, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4088, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4093, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4098, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4103, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 8
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=4130, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4137, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4144, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4157, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4162, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4167, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4172, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4177, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4182, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4187, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4193, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4198, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4203, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4208, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4213, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4218, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4223, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4228, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4233, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 9
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=4264, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4271, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4278, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4291, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4296, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4301, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4306, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4311, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4316, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4321, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4327, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4332, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4337, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4342, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4347, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4352, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4357, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4362, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4367, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


###############################################################################
# Class 0S
###############################################################################
class TestClassGetCallerInfo0S(TestClassGetCallerInfo0):
    """Subclass to get caller info0."""

    ###########################################################################
    # Class 0S Method 1
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=4399, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4406, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4413, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4426, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4431, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4436, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4441, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4446, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4451, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4456, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4462, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4467, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4472, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4477, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4482, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4487, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4492, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4497, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4502, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 2
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=4528, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4535, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4542, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4555, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4560, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4565, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4570, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4575, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4580, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4585, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4591, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4596, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4601, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4606, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4611, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4616, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4621, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4626, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4631, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 3
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=4658, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4665, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4672, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4685, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4690, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4695, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4700, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4705, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4710, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4715, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4721, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4726, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4731, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4736, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4741, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4746, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4751, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4756, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4761, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 4
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=4787, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4794, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4801, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4814, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4819, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4824, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4829, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4834, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4839, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4844, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4850, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4855, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4860, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4865, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4870, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=4875, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=4880, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=4885, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=4890, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 5
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=4916, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=4923, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=4930, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=4943, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=4948, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=4953, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=4958, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=4963, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=4968, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=4973, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=4979, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=4984, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=4989, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=4994, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=4999, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5004, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5009, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5014, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5019, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 6
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=5046, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5053, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5060, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5073, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5078, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5083, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5088, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5093, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5098, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5103, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5109, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5114, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5119, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5124, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5129, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5134, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5139, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5144, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5149, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 7
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=5175, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5182, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5189, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5202, add=0)
        self.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        update_stack(exp_stack=exp_stack, line_num=5205, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5208, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5212, add=0)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5214, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5216, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5219, add=1)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5224, add=0)
        super().test_get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5226, add=1)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5229, add=1)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5234, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5239, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5244, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5249, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5254, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5259, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5264, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5270, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5275, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5280, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5285, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5290, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5295, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5300, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5305, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5310, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 8
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=5336, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5343, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5350, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5364, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5367, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5371, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5374, add=1)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=5379, add=1)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5382, add=1)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5387, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5392, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5397, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5402, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5407, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5412, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5417, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5423, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5428, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5433, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5438, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5443, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5448, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5453, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5458, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5463, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 9
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=5490, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5497, add=0)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        update_stack(exp_stack=exp_stack, line_num=5504, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5518, add=0)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        update_stack(exp_stack=exp_stack, line_num=5521, add=0)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=5525, add=1)
        cls.get_caller_info_s0bt(exp_stack=exp_stack,
                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5528, add=0)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5530, add=1)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=5533, add=1)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)
        # call module level function
        update_stack(exp_stack=exp_stack, line_num=5537, add=0)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=5542, add=1)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5547, add=1)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5552, add=1)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5557, add=1)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5562, add=1)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5567, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=5573, add=1)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5578, add=1)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5583, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5588, add=1)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5593, add=1)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5598, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5603, add=1)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5608, add=1)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5613, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


###############################################################################
# Class 1
###############################################################################
class ClassGetCallerInfo1:
    """Class to get caller info1."""

    def __init__(self) -> None:
        """The initialization."""
        self.var1 = 1

    ###########################################################################
    # Class 1 Method 1
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=5652, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5659, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=5666, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5681, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=5686, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5691, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5696, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5701, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5706, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5711, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=5717, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5722, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5727, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5732, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5737, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5742, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5747, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5752, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5757, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1 Method 2
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=5784, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5791, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=5798, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5813, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=5818, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5823, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5828, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5833, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5838, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5843, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=5849, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5854, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5859, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5864, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=5869, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=5874, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=5879, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=5884, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=5889, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1 Method 3
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=5916, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=5923, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=5930, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=5945, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=5950, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=5955, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=5960, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=5965, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=5970, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=5975, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=5981, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=5986, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=5991, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=5996, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6001, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6006, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6011, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6016, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6021, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1 Method 4
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=6048, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6055, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6062, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6077, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6082, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6087, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6092, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6097, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6102, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6107, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6113, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6118, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6123, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6128, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6133, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6138, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6143, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6148, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6153, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1 Method 5
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=6180, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6187, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6194, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6209, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6214, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6219, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6224, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6229, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6234, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6239, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6245, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6250, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6255, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6260, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6265, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6270, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6275, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6280, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6285, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1 Method 6
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=6313, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6320, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6327, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6342, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6347, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6352, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6357, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6362, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6367, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6372, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6378, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6383, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6388, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6393, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6398, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6403, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6408, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6413, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6418, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1 Method 7
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=6446, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6453, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6460, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6475, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6480, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6485, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6490, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6495, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6500, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6505, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6511, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6516, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6521, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6526, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6531, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6536, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6541, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6546, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6551, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1 Method 8
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=6578, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6585, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6592, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6607, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6612, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6617, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6622, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6627, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6632, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6637, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6643, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6648, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6653, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6658, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6663, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6668, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6673, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6678, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6683, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1 Method 9
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=6711, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6718, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6725, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6740, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6745, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6750, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6755, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6760, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6765, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6770, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6776, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6781, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6786, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6791, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6796, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6801, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6806, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6811, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6816, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


###############################################################################
# Class 1S
###############################################################################
class ClassGetCallerInfo1S(ClassGetCallerInfo1):
    """Subclass to get caller info1."""

    def __init__(self) -> None:
        """The initialization for subclass 1."""
        super().__init__()
        self.var2 = 2

    ###########################################################################
    # Class 1S Method 1
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=6855, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6862, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=6869, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=6884, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=6889, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=6894, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=6899, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=6904, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=6909, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=6914, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=6920, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=6925, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=6930, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=6935, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=6940, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=6945, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=6950, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=6955, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=6960, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1S Method 2
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=6987, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=6994, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7001, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7016, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7021, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7026, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7031, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7036, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7041, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7046, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7052, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7057, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7062, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7067, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7072, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7077, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7082, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7087, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7092, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1S Method 3
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=7120, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7127, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7134, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7149, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7154, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7159, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7164, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7169, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7174, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7179, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7185, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7190, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7195, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7200, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7205, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7210, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7215, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7220, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7225, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1S Method 4
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=7252, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7259, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7266, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7281, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7286, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7291, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7296, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7301, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7306, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7311, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7317, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7322, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7327, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7332, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7337, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7342, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7347, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7352, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7357, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1S Method 5
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=7384, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7391, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7398, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7413, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7418, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7423, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7428, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7433, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7438, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7443, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7449, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7454, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7459, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7464, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7469, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7474, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7479, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7484, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7489, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1S Method 6
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=7517, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7524, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7531, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7546, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7551, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7556, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7561, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7566, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7571, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7576, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7582, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7587, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7592, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7597, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7602, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7607, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7612, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7617, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7622, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1S Method 7
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=7649, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7656, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7663, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7678, add=0)
        self.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1 = ClassGetCallerInfo1()
        update_stack(exp_stack=exp_stack, line_num=7681, add=1)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7685, add=1)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7690, add=0)
        self.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7692, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7694, add=1)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7697, add=1)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7702, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7704, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7707, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7712, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7717, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7722, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7727, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7732, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7737, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7742, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7748, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7753, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7758, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7763, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7768, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7773, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7778, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7783, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7788, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1S Method 8
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=7815, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7822, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7829, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=7845, add=1)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=7849, add=1)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=7854, add=1)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7857, add=1)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=7862, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=7865, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=7870, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=7875, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=7880, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=7885, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=7890, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=7895, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=7900, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=7906, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=7911, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=7916, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=7921, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=7926, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=7931, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=7936, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=7941, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=7946, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 1S Method 9
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=7974, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=7981, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=7988, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8004, add=1)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        update_stack(exp_stack=exp_stack, line_num=8008, add=1)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=8013, add=1)
        cls.get_caller_info_s1bt(exp_stack=exp_stack,
                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8016, add=0)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8018, add=1)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8021, add=1)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=8026, add=0)
        cls.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8028, add=0)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8030, add=1)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=8033, add=1)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=8038, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=8043, add=1)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8048, add=1)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8053, add=1)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8058, add=1)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8063, add=1)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8068, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=8074, add=1)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8079, add=1)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8084, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8089, add=1)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8094, add=1)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8099, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8104, add=1)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8109, add=1)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8114, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


###############################################################################
# Class 2
###############################################################################
class ClassGetCallerInfo2:
    """Class to get caller info2."""

    def __init__(self) -> None:
        """The initialization."""
        self.var1 = 1

    ###########################################################################
    # Class 2 Method 1
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=8153, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8160, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8167, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8182, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8187, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8192, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8197, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8202, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8207, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8212, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8218, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8223, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8228, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8233, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8238, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8243, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8248, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8253, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8258, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2 Method 2
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=8285, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8292, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8299, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8314, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8319, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8324, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8329, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8334, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8339, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8344, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8350, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8355, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8360, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8365, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8370, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8375, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8380, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8385, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8390, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2 Method 3
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=8417, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8424, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8431, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8446, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8451, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8456, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8461, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8466, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8471, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8476, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8482, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8487, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8492, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8497, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8502, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8507, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8512, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8517, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8522, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2 Method 4
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=8549, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8556, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8563, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8578, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8583, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8588, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8593, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8598, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8603, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8608, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8614, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8619, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8624, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8629, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8634, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8639, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8644, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8649, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8654, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2 Method 5
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=8681, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8688, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8695, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8710, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8715, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8720, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8725, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8730, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8735, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8740, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8746, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8751, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8756, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8761, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8766, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8771, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8776, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8781, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8786, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2 Method 6
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=8814, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8821, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8828, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8843, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8848, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8853, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8858, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8863, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=8868, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=8873, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=8879, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=8884, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=8889, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=8894, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=8899, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=8904, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=8909, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=8914, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=8919, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2 Method 7
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=8947, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=8954, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=8961, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=8976, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=8981, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=8986, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=8991, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=8996, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9001, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9006, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9012, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9017, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9022, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9027, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9032, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9037, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9042, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9047, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9052, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2 Method 8
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=9079, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9086, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9093, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9108, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9113, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9118, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9123, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9128, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9133, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9138, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9144, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9149, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9154, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9159, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9164, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9169, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9174, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9179, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9184, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2 Method 9
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=9212, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9219, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9226, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9241, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9246, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9251, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9256, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9261, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9266, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9271, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9277, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9282, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9287, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9292, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9297, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9302, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9307, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9312, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9317, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


###############################################################################
# Class 2S
###############################################################################
class ClassGetCallerInfo2S(ClassGetCallerInfo2):
    """Subclass to get caller info2."""

    def __init__(self) -> None:
        """The initialization for subclass 2."""
        super().__init__()
        self.var2 = 2

    ###########################################################################
    # Class 2S Method 1
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=9356, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9363, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9370, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9385, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9390, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9395, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9400, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9405, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9410, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9415, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9421, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9426, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9431, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9436, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9441, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9446, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9451, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9456, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9461, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2S Method 2
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=9488, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9495, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9502, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9517, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9522, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9527, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9532, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9537, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9542, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9547, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9553, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9558, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9563, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9568, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9573, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9578, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9583, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9588, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9593, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2S Method 3
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=9621, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9628, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9635, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9650, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9655, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9660, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9665, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9670, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9675, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9680, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9686, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9691, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9696, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9701, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9706, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9711, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9716, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9721, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9726, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2S Method 4
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=9753, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9760, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9767, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9782, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9787, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9792, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9797, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9802, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9807, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9812, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9818, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9823, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9828, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9833, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9838, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9843, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9848, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9853, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9858, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2S Method 5
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=9885, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=9892, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=9899, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=9914, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=9919, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=9924, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=9929, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=9934, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=9939, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=9944, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=9950, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=9955, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=9960, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=9965, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=9970, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=9975, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=9980, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=9985, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=9990, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2S Method 6
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=10018, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10025, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10032, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10047, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10052, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10057, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10062, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10067, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10072, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10077, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10083, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10088, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10093, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10098, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10103, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10108, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10113, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10118, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10123, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2S Method 7
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=10150, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10157, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10164, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10179, add=0)
        self.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2 = ClassGetCallerInfo2()
        update_stack(exp_stack=exp_stack, line_num=10182, add=1)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10186, add=1)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10191, add=0)
        self.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10193, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10195, add=1)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10198, add=1)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10203, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10205, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10208, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10213, add=0)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10218, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10223, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10228, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10233, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10238, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10243, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10249, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10254, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10259, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10264, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10269, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10274, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10279, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10284, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10289, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2S Method 8
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=10316, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10323, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10330, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10346, add=1)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10350, add=1)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10355, add=1)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10358, add=1)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10363, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10366, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10371, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10376, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10381, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10386, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10391, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10396, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10401, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10407, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10412, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10417, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10422, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10427, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10432, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10437, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10442, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10447, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 2S Method 9
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=10475, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10482, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10489, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=10505, add=1)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        update_stack(exp_stack=exp_stack, line_num=10509, add=1)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=10514, add=1)
        cls.get_caller_info_s2bt(exp_stack=exp_stack,
                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10517, add=0)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10519, add=1)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10522, add=1)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=10527, add=0)
        cls.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10529, add=0)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10531, add=1)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=10534, add=1)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        update_stack(exp_stack=exp_stack, line_num=10539, add=0)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=10544, add=1)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        update_stack(exp_stack=exp_stack, line_num=10549, add=1)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        update_stack(exp_stack=exp_stack, line_num=10554, add=1)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        update_stack(exp_stack=exp_stack, line_num=10559, add=1)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        update_stack(exp_stack=exp_stack, line_num=10564, add=1)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        update_stack(exp_stack=exp_stack, line_num=10569, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=10575, add=1)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        update_stack(exp_stack=exp_stack, line_num=10580, add=1)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        update_stack(exp_stack=exp_stack, line_num=10585, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        update_stack(exp_stack=exp_stack, line_num=10590, add=1)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        update_stack(exp_stack=exp_stack, line_num=10595, add=1)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        update_stack(exp_stack=exp_stack, line_num=10600, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        update_stack(exp_stack=exp_stack, line_num=10605, add=1)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        update_stack(exp_stack=exp_stack, line_num=10610, add=1)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        update_stack(exp_stack=exp_stack, line_num=10615, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


###############################################################################
# Class 3
###############################################################################
class ClassGetCallerInfo3:
    """Class to get caller info3."""

    def __init__(self) -> None:
        """The initialization."""
        self.var1 = 1

    ###########################################################################
    # Class 3 Method 1
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=10654, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10661, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10668, add=0)
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

    ###########################################################################
    # Class 3 Method 2
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=10705, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10712, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10719, add=0)
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

    ###########################################################################
    # Class 3 Method 3
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=10756, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10763, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10770, add=0)
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

    ###########################################################################
    # Class 3 Method 4
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=10807, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10814, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10821, add=0)
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

    ###########################################################################
    # Class 3 Method 5
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=10858, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10865, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10872, add=0)
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

    ###########################################################################
    # Class 3 Method 6
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=10910, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10917, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10924, add=0)
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

    ###########################################################################
    # Class 3 Method 7
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=10962, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=10969, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=10976, add=0)
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

    ###########################################################################
    # Class 3 Method 8
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=11013, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11020, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11027, add=0)
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

    ###########################################################################
    # Class 3 Method 9
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=11065, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11072, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11079, add=0)
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


###############################################################################
# Class 3S
###############################################################################
class ClassGetCallerInfo3S(ClassGetCallerInfo3):
    """Subclass to get caller info3."""

    def __init__(self) -> None:
        """The initialization for subclass 3."""
        super().__init__()
        self.var2 = 2

    ###########################################################################
    # Class 3S Method 1
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=11128, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11135, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11142, add=0)
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

    ###########################################################################
    # Class 3S Method 2
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=11179, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11186, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11193, add=0)
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

    ###########################################################################
    # Class 3S Method 3
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=11231, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11238, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11245, add=0)
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

    ###########################################################################
    # Class 3S Method 4
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=11282, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11289, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11296, add=0)
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

    ###########################################################################
    # Class 3S Method 5
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=11333, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11340, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11347, add=0)
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

    ###########################################################################
    # Class 3S Method 6
    ###########################################################################
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

    ###########################################################################
    # Class 3S Method 7
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=11436, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11443, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11450, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11465, add=0)
        self.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3 = ClassGetCallerInfo3()
        update_stack(exp_stack=exp_stack, line_num=11468, add=1)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11472, add=1)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11477, add=0)
        self.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11479, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11481, add=1)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11484, add=1)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11489, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11491, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11494, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 3S Method 8
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=11521, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11528, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11535, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11551, add=1)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11555, add=1)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11560, add=1)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11563, add=1)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11568, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11571, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 3S Method 9
    ###########################################################################
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
        update_stack(exp_stack=exp_stack, line_num=11599, add=0)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        update_stack(exp_stack=exp_stack, line_num=11606, add=0)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            update_stack(exp_stack=exp_stack, line_num=11613, add=0)
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
        update_stack(exp_stack=exp_stack, line_num=11629, add=1)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        update_stack(exp_stack=exp_stack, line_num=11633, add=1)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        update_stack(exp_stack=exp_stack, line_num=11638, add=1)
        cls.get_caller_info_s3bt(exp_stack=exp_stack,
                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11641, add=0)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11643, add=1)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11646, add=1)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        update_stack(exp_stack=exp_stack, line_num=11651, add=0)
        cls.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11653, add=0)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11655, add=1)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        update_stack(exp_stack=exp_stack, line_num=11658, add=1)
        ClassGetCallerInfo3S.get_caller_info_c3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


#######################################################################
# following tests needs to be at module level (i.e., script form)
#######################################################################

#######################################################################
# test get_caller_info from module (script) level
#######################################################################
exp_stack0: Deque[CallerInfo] = deque()
exp_caller_info0 = CallerInfo(mod_name='test_diag_msg.py',
                              cls_name='',
                              func_name='',
                              line_num=9921)

exp_stack0.append(exp_caller_info0)
update_stack(exp_stack=exp_stack0, line_num=11682, add=0)
for i0, expected_caller_info0 in enumerate(list(reversed(exp_stack0))):
    try:
        frame0 = _getframe(i0)
        caller_info0 = get_caller_info(frame0)
    finally:
        del frame0
    assert caller_info0 == expected_caller_info0

###############################################################################
# test get_formatted_call_sequence from module (script) level
###############################################################################
update_stack(exp_stack=exp_stack0, line_num=11691, add=0)
call_seq0 = get_formatted_call_sequence(depth=1)

assert call_seq0 == get_exp_seq(exp_stack=exp_stack0)

###############################################################################
# test diag_msg from module (script) level
# note that this is just a smoke test and is only visually verified
###############################################################################
diag_msg()  # basic, empty msg
diag_msg('hello')
diag_msg(depth=2)
diag_msg('hello2', depth=3)
diag_msg(depth=4, end='\n\n')
diag_msg('hello3', depth=5, end='\n\n')

# call module level function
update_stack(exp_stack=exp_stack0, line_num=11708, add=0)
func_get_caller_info_1(exp_stack=exp_stack0, capsys=None)

# call method
cls_get_caller_info01 = ClassGetCallerInfo1()
update_stack(exp_stack=exp_stack0, line_num=11713, add=0)
cls_get_caller_info01.get_caller_info_m1(exp_stack=exp_stack0, capsys=None)

# call static method
update_stack(exp_stack=exp_stack0, line_num=11717, add=0)
cls_get_caller_info01.get_caller_info_s1(exp_stack=exp_stack0, capsys=None)

# call class method
update_stack(exp_stack=exp_stack0, line_num=11721, add=0)
ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack0, capsys=None)

# call overloaded base class method
update_stack(exp_stack=exp_stack0, line_num=11725, add=0)
cls_get_caller_info01.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class static method
update_stack(exp_stack=exp_stack0, line_num=11729, add=0)
cls_get_caller_info01.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class class method
update_stack(exp_stack=exp_stack0, line_num=11733, add=0)
ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call subclass method
cls_get_caller_info01S = ClassGetCallerInfo1S()
update_stack(exp_stack=exp_stack0, line_num=11738, add=0)
cls_get_caller_info01S.get_caller_info_m1s(exp_stack=exp_stack0, capsys=None)

# call subclass static method
update_stack(exp_stack=exp_stack0, line_num=11742, add=0)
cls_get_caller_info01S.get_caller_info_s1s(exp_stack=exp_stack0, capsys=None)

# call subclass class method
update_stack(exp_stack=exp_stack0, line_num=11746, add=0)
ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass method
update_stack(exp_stack=exp_stack0, line_num=11750, add=0)
cls_get_caller_info01S.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass static method
update_stack(exp_stack=exp_stack0, line_num=11754, add=0)
cls_get_caller_info01S.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass class method
update_stack(exp_stack=exp_stack0, line_num=11758, add=0)
ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call base method from subclass method
update_stack(exp_stack=exp_stack0, line_num=11762, add=0)
cls_get_caller_info01S.get_caller_info_m1sb(exp_stack=exp_stack0, capsys=None)

# call base static method from subclass static method
update_stack(exp_stack=exp_stack0, line_num=11766, add=0)
cls_get_caller_info01S.get_caller_info_s1sb(exp_stack=exp_stack0, capsys=None)

# call base class method from subclass class method
update_stack(exp_stack=exp_stack0, line_num=11770, add=0)
ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack0, capsys=None)
