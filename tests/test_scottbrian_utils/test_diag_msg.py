"""test_diag_msg.py module."""

from datetime import datetime
# noinspection PyProtectedMember
from sys import _getframe
import sys
from typing import Any, cast, Deque, Final, List, NamedTuple, Optional, \
    TextIO, Union

import pytest
from collections import deque

from scottbrian_utils.diag_msg import get_caller_info
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.diag_msg import diag_msg
from scottbrian_utils.diag_msg import CallerInfo
from scottbrian_utils.diag_msg import diag_msg_datetime_fmt
from scottbrian_utils.diag_msg import get_formatted_call_seq_depth
from scottbrian_utils.diag_msg import diag_msg_caller_depth


class DiagMsgArgs(NamedTuple):
    """Structure for the testing various args for diag_msg."""
    arg_bits: int
    dt_format_arg: str
    depth_arg: int
    msg_arg: List[str]
    file_arg: str


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


latest_arg_list = [None, 0, 1, 2, 3]


@pytest.fixture(params=latest_arg_list)  # type: ignore
def latest_arg(request: Any) -> Union[int, None]:
    """Using different depth args.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param  # cast(int, request.param)

msg_arg_list = [[None],
                ['one-word'],
                ['two words'],
                ['three + four'],
                ['two', 'items'],
                ['three', 'items', 'for you']]


@pytest.fixture(params=msg_arg_list)  # type: ignore
def msg_arg(request: Any) -> List[str]:
    """Using different message arg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


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
        end: Specifies one entry earlier then the earliest entry to return

    Returns:
          A slice of the input call sequence string
    """
    seq_items = call_seq.split(' -> ')
    adj_end = len(seq_items) - start
    adj_start = 0 if end is None else len(seq_items) - end

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
                    file_arg: str,
                    exp_msg: List[Any],
                    depth: Optional[int] = None,
                    dt_format: str = diag_msg_datetime_fmt) -> None:
    """Verify the captured msg is as expected.

    Args:
        exp_stack: The expected stack of callers
        before_time: The time just before issuing the diag_msg
        after_time: The time just after the diag_msg
        capsys: Pytest fixture that captures output
        file_arg: Specifies whether to use sys.stdout or sys.stderr
        exp_msg: A list of the expected message parts
        depth: Specifies how many call entries to verify
        dt_format: Specifies the datetime format being used for diag_msg

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
    if dt_format == None:
        dt_format = diag_msg_datetime_fmt
    before_time = datetime.strptime(
        before_time.strftime(dt_format), dt_format)
    after_time = datetime.strptime(
        after_time.strftime(dt_format), dt_format)

    if file_arg == 'sys.stderr':
        cap_msg = capsys.readouterr().err
    else:
        cap_msg = capsys.readouterr().out

    str_list = cap_msg.split()
    dt_format_split_list = dt_format.split()
    msg_time_str = ''
    for i in range(len(dt_format_split_list)):
        msg_time_str = f'{msg_time_str}{str_list.pop(0)} '
    msg_time_str = msg_time_str.rstrip()
    msg_time = datetime.strptime(msg_time_str, dt_format)
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
                    seq_depth=depth)

    captured_msg = ''
    for i in range(len(str_list)):
        captured_msg = f'{captured_msg}{str_list[i]} '
    captured_msg = captured_msg.rstrip()

    check_msg = ''
    for i in range(len(exp_msg)):
        check_msg = f'{check_msg}{exp_msg[i]} '
    check_msg = check_msg.rstrip()

    assert captured_msg == check_msg


###############################################################################
# verify_diag_msg is a helper function used by many test cases
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
                 line_num: int) -> None:
    caller_info = exp_stack.pop()
    caller_info = caller_info._replace(line_num=line_num)
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
                                     line_num=396)
        exp_stack.append(exp_caller_info)
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
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='test_get_call_seq_with_parms',
                                     line_num=423)
        exp_stack.append(exp_caller_info)
        call_seq = ''
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=426)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=429)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=432)
            call_seq = get_formatted_call_sequence(latest=latest_arg,
                                                   depth=depth_arg)
        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_latest=latest_arg,
                        seq_depth=depth_arg)

        update_stack(exp_stack=exp_stack, line_num=440)
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
                                     line_num=468)
        exp_stack.append(exp_caller_info)
        call_seq = ''
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=471)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=474)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=477)
            call_seq = get_formatted_call_sequence(latest=latest_arg,
                                                   depth=depth_arg)
        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_latest=latest_arg,
                        seq_depth=depth_arg)

        update_stack(exp_stack=exp_stack, line_num=485)
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
                                     line_num=515)
        exp_stack.append(exp_caller_info)
        call_seq = ''
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=518)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=521)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=524)
            call_seq = get_formatted_call_sequence(latest=latest_arg,
                                                   depth=depth_arg)
        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_latest=latest_arg,
                        seq_depth=depth_arg)

        update_stack(exp_stack=exp_stack, line_num=532)
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
                                     line_num=562)
        exp_stack.append(exp_caller_info)
        call_seq = ''
        if latest_arg is None and depth_arg is None:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=565)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg is None:
            update_stack(exp_stack=exp_stack, line_num=568)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg is not None:
            update_stack(exp_stack=exp_stack, line_num=571)
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
    def test_get_call_seq_full_stack(self):
        """Test to ensure we can run the entire stack."""
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='test_get_call_seq_full_stack',
                                     line_num=594)
        exp_stack.append(exp_caller_info)
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
                          dt_format_arg: str,
                          depth_arg: int,
                          msg_arg: List[str],
                          file_arg: str
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

        a_msg_arg = ['']
        if depth_arg is not None:
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
                                     line_num=703)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg()
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        file_arg='sys.stdout',
                        exp_msg=[],
                        depth=None)

    ###########################################################################
    # diag_msg with parms
    ###########################################################################
    def test_diag_msg_with_parms(self,
                                 capsys: pytest.CaptureFixture[str],
                                 dt_format_arg: str,
                                 depth_arg: int,
                                 msg_arg: List[str],
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
                                     line_num=745)
        exp_stack.append(exp_caller_info)
        diag_msg_args = self.get_diag_msg_args(dt_format_arg=dt_format_arg,
                                               depth_arg=depth_arg,
                                               msg_arg=msg_arg,
                                               file_arg=file_arg)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=748)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=751)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=754)
            diag_msg(*diag_msg_args.msg_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=758)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=761)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=765)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=769)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=774)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=777)
            diag_msg(dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=781)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=785)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=790)
            diag_msg(depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=794)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg),
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=799)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=804)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))

        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        file_arg=diag_msg_args.file_arg,
                        exp_msg=diag_msg_args.msg_arg,
                        depth=diag_msg_args.depth_arg,
                        dt_format=diag_msg_args.dt_format_arg)

        update_stack(exp_stack=exp_stack, line_num=821)
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
            dt_format_arg: pytest fixture for datetime format
            depth_arg: pytest fixture for number of call seq entries
            msg_arg: pytest fixture for messages
            file_arg: pytest fixture for different print file types

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestDiagMsg',
                                     func_name='diag_msg_depth_2',
                                     line_num=850)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=853)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=856)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=859)
            diag_msg(*diag_msg_args.msg_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=863)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=866)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=870)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=874)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=879)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=882)
            diag_msg(dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=886)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=890)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=895)
            diag_msg(depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=899)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg),
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=904)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=909)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))

        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        file_arg=diag_msg_args.file_arg,
                        exp_msg=diag_msg_args.msg_arg,
                        depth=diag_msg_args.depth_arg,
                        dt_format=diag_msg_args.dt_format_arg)

        update_stack(exp_stack=exp_stack, line_num=926)
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
            dt_format_arg: pytest fixture for datetime format
            depth_arg: pytest fixture for number of call seq entries
            msg_arg: pytest fixture for messages
            file_arg: pytest fixture for different print file types

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestDiagMsg',
                                     func_name='diag_msg_depth_3',
                                     line_num=957)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        if diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE0:
            diag_msg()
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=960)
            diag_msg(file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=963)
            diag_msg(*diag_msg_args.msg_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=966)
            diag_msg(*diag_msg_args.msg_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=970)
            diag_msg(depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=973)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=977)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT0_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=981)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=986)
            diag_msg(dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=989)
            diag_msg(dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=993)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH0_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=997)
            diag_msg(*diag_msg_args.msg_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1002)
            diag_msg(depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG0_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1006)
            diag_msg(depth=diag_msg_args.depth_arg,
                     file=eval(diag_msg_args.file_arg),
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE0:
            update_stack(exp_stack=exp_stack, line_num=1011)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg)
        elif diag_msg_args.arg_bits == TestDiagMsg.DT1_DEPTH1_MSG1_FILE1:
            update_stack(exp_stack=exp_stack, line_num=1016)
            diag_msg(*diag_msg_args.msg_arg,
                     depth=diag_msg_args.depth_arg,
                     dt_format=diag_msg_args.dt_format_arg,
                     file=eval(diag_msg_args.file_arg))

        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys,
                        file_arg=diag_msg_args.file_arg,
                        exp_msg=diag_msg_args.msg_arg,
                        depth=diag_msg_args.depth_arg,
                        dt_format=diag_msg_args.dt_format_arg)

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
                                 line_num=1064)
    exp_stack.append(exp_caller_info)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1073)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=1)

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1082)
    exp_stack.append(exp_caller_info)
    before_time = datetime.now()
    diag_msg('message 0', 0, depth=1)
    after_time = datetime.now()

    verify_diag_msg(exp_stack=exp_stack,
                    before_time=before_time,
                    after_time=after_time,
                    capsys=capsys, file_arg='sys.stdout', 
                    exp_msg=['message', '0', '0'])

    # call module level function
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1095)
    exp_stack.append(exp_caller_info)
    func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info1 = ClassGetCallerInfo1()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1102)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

    # call static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1108)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

    # call class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1114)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1120)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1127)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1134)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info1s = ClassGetCallerInfo1S()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1142)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1149)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1156)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1163)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1170)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1177)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1184)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1191)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1198)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                              capsys=capsys)

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
                                 line_num=1224)
    exp_stack.append(exp_caller_info)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1233)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1243)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=len(exp_stack))
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

    # call module level function
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1256)
    exp_stack.append(exp_caller_info)
    func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info2 = ClassGetCallerInfo2()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1263)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

    # call static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1269)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

    # call class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1275)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1281)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1288)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1295)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info2s = ClassGetCallerInfo2S()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1303)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1310)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1317)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1324)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1331)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1338)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1345)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1352)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1359)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                              capsys=capsys)

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
                                 line_num=1385)
    exp_stack.append(exp_caller_info)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1394)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1404)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 2', 2, depth=len(exp_stack))
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '2', '2'])

    # call module level function
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1417)
    exp_stack.append(exp_caller_info)
    func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info3 = ClassGetCallerInfo3()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1424)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

    # call static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1430)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

    # call class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1436)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1442)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1449)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1456)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info3s = ClassGetCallerInfo3S()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1464)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1471)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1478)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1485)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1492)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1499)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1506)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1513)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1520)
    exp_stack.append(exp_caller_info)
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
                                 line_num=1546)
    exp_stack.append(exp_caller_info)
    for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
        try:
            frame = _getframe(i)
            caller_info = get_caller_info(frame)
        finally:
            del frame
        assert caller_info == expected_caller_info

    # test call sequence
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1555)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1565)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 2', 2, depth=len(exp_stack))
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '2', '2'])

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
                                     line_num=1606)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1615)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1624)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1637)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1644)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1651)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1658)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1665)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1672)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1679)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1687)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1694)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1701)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1708)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1715)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1722)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1729)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1736)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1743)
        exp_stack.append(exp_caller_info)
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
                                     line_num=1766)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1770)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0(exp_stack=exp_stack,
                                                   capsys=capsys)

        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1776)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1780)
        exp_stack.append(exp_caller_info)
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
                                     line_num=1801)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1810)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1819)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=2)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1832)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1839)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1846)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1853)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1860)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1867)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1874)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1882)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1889)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1896)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1903)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1910)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1917)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1924)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1931)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1938)
        exp_stack.append(exp_caller_info)
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
                                     line_num=1963)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1972)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1981)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1994)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2001)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2008)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2015)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2022)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2029)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2036)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2044)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2051)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2058)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2065)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2072)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2079)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2086)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2093)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2100)
        exp_stack.append(exp_caller_info)
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
                                     line_num=2125)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2134)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2143)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2156)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2163)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2170)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2177)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2184)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2191)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2198)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2206)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2213)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2220)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2227)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2234)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2241)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2248)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2255)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2262)
        exp_stack.append(exp_caller_info)
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
                                     line_num=2287)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2296)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2305)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2318)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2325)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2332)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2339)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2346)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2353)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2360)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2368)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2375)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2382)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2389)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2396)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2403)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2410)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2417)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2424)
        exp_stack.append(exp_caller_info)
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
                                     line_num=2450)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2459)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2468)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2481)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2488)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2495)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2502)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2509)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2516)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2523)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2531)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2538)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2545)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2552)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2559)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2566)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2573)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2580)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2587)
        exp_stack.append(exp_caller_info)
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
                                     line_num=2612)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2621)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2630)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=len(exp_stack))
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2643)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2650)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2657)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2664)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2671)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2678)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2685)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2693)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2700)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2707)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2714)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2721)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2728)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2735)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2742)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2749)
        exp_stack.append(exp_caller_info)
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
                                     line_num=2775)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2784)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2793)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=len(exp_stack))
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2806)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2813)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2820)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2827)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2834)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2841)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2848)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2856)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2863)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2870)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2877)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2884)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2891)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2898)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2905)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2912)
        exp_stack.append(exp_caller_info)
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
                                     line_num=2942)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2951)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2960)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=len(exp_stack))
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2973)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2980)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2987)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2994)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3001)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3008)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3015)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3023)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3030)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3037)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3044)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3051)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3058)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3065)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3072)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3079)
        exp_stack.append(exp_caller_info)
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
                                     line_num=3110)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3119)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3128)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3141)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3148)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3155)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3162)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3169)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3176)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3183)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3191)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3198)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3205)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3212)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3219)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3226)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3233)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3240)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3247)
        exp_stack.append(exp_caller_info)
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
                                     line_num=3272)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3281)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3290)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3303)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3310)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3317)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3324)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3331)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3338)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3345)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3353)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3360)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3367)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3374)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3381)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3388)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3395)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3402)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3409)
        exp_stack.append(exp_caller_info)
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
                                     line_num=3435)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3444)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3453)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3466)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3473)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3480)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3487)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3494)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3501)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3508)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3516)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3523)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3530)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3537)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3544)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3551)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3558)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3565)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3572)
        exp_stack.append(exp_caller_info)
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
                                     line_num=3597)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3606)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3615)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3628)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3635)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3642)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3649)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3656)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3663)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3670)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3678)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3685)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3692)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3699)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3706)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3713)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3720)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3727)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3734)
        exp_stack.append(exp_caller_info)
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
                                     line_num=3759)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3768)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3777)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3790)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3797)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3804)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3811)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3818)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3825)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3832)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3840)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3847)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3854)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3861)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3868)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3875)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3882)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3889)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3896)
        exp_stack.append(exp_caller_info)
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
                                     line_num=3922)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3931)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3940)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3953)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3960)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3967)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3974)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3981)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3988)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3995)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4003)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4010)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4017)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4024)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4031)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4038)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4045)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4052)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4059)
        exp_stack.append(exp_caller_info)
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
                                     line_num=4084)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4093)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4102)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call base class normal method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4115)
        exp_stack.append(exp_caller_info)
        self.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4120)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4125)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4131)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4135)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4139)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4144)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4151)
        exp_stack.append(exp_caller_info)
        super().test_get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4155)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4160)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4167)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4174)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4181)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4188)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4195)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4202)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4209)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4217)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4224)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4231)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4238)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4245)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4252)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4259)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4266)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4273)
        exp_stack.append(exp_caller_info)
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
                                     line_num=4298)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4307)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4316)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call base class normal method target
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4330)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4335)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4341)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4346)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4353)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4358)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4365)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4372)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4379)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4386)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4393)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4400)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4407)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4415)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4422)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4429)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4436)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4443)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4450)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4457)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4464)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4471)
        exp_stack.append(exp_caller_info)
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
                                     line_num=4497)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4506)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4515)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()

        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        capsys=capsys, file_arg='sys.stdout', 
                        exp_msg=['message', '1', '1'])

        # call base class normal method target
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4529)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4534)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4540)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s0bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4545)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4549)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4554)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)
        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4560)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4567)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4574)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4581)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4588)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4595)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4602)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4610)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4617)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4624)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4631)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4638)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4645)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4652)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4659)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4666)
        exp_stack.append(exp_caller_info)
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
                                     line_num=4704)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4713)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4722)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4735)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4742)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4749)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4756)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4763)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4770)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4777)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4785)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4792)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4799)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4806)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4813)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4820)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4827)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4834)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4841)
        exp_stack.append(exp_caller_info)
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
                                     line_num=4867)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4876)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4885)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4898)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4905)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4912)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4919)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4926)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4933)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4940)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4948)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4955)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4962)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4969)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4976)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4983)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4990)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4997)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5004)
        exp_stack.append(exp_caller_info)
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
                                     line_num=5030)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5039)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5048)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5061)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5068)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5075)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5082)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5089)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5096)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5103)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5111)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5118)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5125)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5132)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5139)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5146)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5153)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5160)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5167)
        exp_stack.append(exp_caller_info)
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
                                     line_num=5193)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5202)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5211)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5224)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5231)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5238)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5245)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5252)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5259)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5266)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5274)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5281)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5288)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5295)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5302)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5309)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5316)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5323)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5330)
        exp_stack.append(exp_caller_info)
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
                                     line_num=5356)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5365)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5374)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5387)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5394)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5401)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5408)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5415)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5422)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5429)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5437)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5444)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5451)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5458)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5465)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5472)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5479)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5486)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5493)
        exp_stack.append(exp_caller_info)
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
                                     line_num=5520)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5529)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5538)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5551)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5558)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5565)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5572)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5579)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5586)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5593)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5601)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5608)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5615)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5622)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5629)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5636)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5643)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5650)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5657)
        exp_stack.append(exp_caller_info)
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
                                     line_num=5684)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5693)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5702)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5715)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5722)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5729)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5736)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5743)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5750)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5757)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5765)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5772)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5779)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5786)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5793)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5800)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5807)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5814)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5821)
        exp_stack.append(exp_caller_info)
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
                                     line_num=5847)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5856)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5865)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5878)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5885)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5892)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5899)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5906)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5913)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5920)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5928)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5935)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5942)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5949)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5956)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5963)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5970)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5977)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5984)
        exp_stack.append(exp_caller_info)
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
                                     line_num=6011)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6020)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6029)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6042)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6049)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6056)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6063)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6070)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6077)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6084)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6092)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6099)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6106)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6113)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6120)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6127)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6134)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6141)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6148)
        exp_stack.append(exp_caller_info)
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
                                     line_num=6186)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6195)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6204)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6217)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6224)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6231)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6238)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6245)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6252)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6259)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6267)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6274)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6281)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6288)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6295)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6302)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6309)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6316)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6323)
        exp_stack.append(exp_caller_info)
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
                                     line_num=6349)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6358)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6367)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6380)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6387)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6394)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6401)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6408)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6415)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6422)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6430)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6437)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6444)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6451)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6458)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6465)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6472)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6479)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6486)
        exp_stack.append(exp_caller_info)
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
                                     line_num=6513)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6522)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6531)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6544)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6551)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6558)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6565)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6572)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6579)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6586)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6594)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6601)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6608)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6615)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6622)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6629)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6636)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6643)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6650)
        exp_stack.append(exp_caller_info)
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
                                     line_num=6676)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6685)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6694)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6707)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6714)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6721)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6728)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6735)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6742)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6749)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6757)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6764)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6771)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6778)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6785)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6792)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6799)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6806)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6813)
        exp_stack.append(exp_caller_info)
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
                                     line_num=6839)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6848)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6857)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6870)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6877)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6884)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6891)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6898)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6905)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6912)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6920)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6927)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6934)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6941)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6948)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6955)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6962)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6969)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6976)
        exp_stack.append(exp_caller_info)
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
                                     line_num=7003)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7012)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7021)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7034)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7041)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7048)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7055)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7062)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7069)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7076)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7084)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7091)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7098)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7105)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7112)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7119)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7126)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7133)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7140)
        exp_stack.append(exp_caller_info)
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
                                     line_num=7166)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7175)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7184)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7197)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7202)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7208)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7215)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7219)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7223)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7228)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7235)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7239)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7244)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7251)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7258)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7265)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7272)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7279)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7286)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7293)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7301)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7308)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7315)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7322)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7329)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7336)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7343)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7350)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7357)
        exp_stack.append(exp_caller_info)
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
                                     line_num=7383)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7392)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7401)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7415)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7421)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7428)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7433)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7440)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7445)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7452)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7459)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7466)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7473)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7480)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7487)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7494)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7502)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7509)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7516)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7523)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7530)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7537)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7544)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7551)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7558)
        exp_stack.append(exp_caller_info)
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
                                     line_num=7585)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7594)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7603)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7617)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7623)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7630)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s1bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7635)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7639)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7644)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7651)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7655)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7659)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7664)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7671)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7678)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7685)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7692)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7699)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7706)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7713)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7721)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7728)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7735)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7742)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7749)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7756)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7763)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7770)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7777)
        exp_stack.append(exp_caller_info)
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
                                     line_num=7815)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7824)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7833)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7846)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7853)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7860)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7867)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7874)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7881)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7888)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7896)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7903)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7910)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7917)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7924)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7931)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7938)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7945)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7952)
        exp_stack.append(exp_caller_info)
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
                                     line_num=7978)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7987)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7996)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8009)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8016)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8023)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8030)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8037)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8044)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8051)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8059)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8066)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8073)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8080)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8087)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8094)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8101)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8108)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8115)
        exp_stack.append(exp_caller_info)
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
                                     line_num=8141)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8150)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8159)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8172)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8179)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8186)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8193)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8200)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8207)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8214)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8222)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8229)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8236)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8243)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8250)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8257)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8264)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8271)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8278)
        exp_stack.append(exp_caller_info)
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
                                     line_num=8304)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8313)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8322)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8335)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8342)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8349)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8356)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8363)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8370)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8377)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8385)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8392)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8399)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8406)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8413)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8420)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8427)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8434)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8441)
        exp_stack.append(exp_caller_info)
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
                                     line_num=8467)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8476)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8485)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8498)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8505)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8512)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8519)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8526)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8533)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8540)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8548)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8555)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8562)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8569)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8576)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8583)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8590)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8597)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8604)
        exp_stack.append(exp_caller_info)
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
                                     line_num=8631)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8640)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8649)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8662)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8669)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8676)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8683)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8690)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8697)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8704)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8712)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8719)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8726)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8733)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8740)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8747)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8754)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8761)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8768)
        exp_stack.append(exp_caller_info)
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
                                     line_num=8795)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8804)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8813)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8826)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8833)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8840)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8847)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8854)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8861)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8868)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8876)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8883)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8890)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8897)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8904)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8911)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8918)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8925)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8932)
        exp_stack.append(exp_caller_info)
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
                                     line_num=8958)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8967)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8976)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8989)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8996)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9003)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9010)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9017)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9024)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9031)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9039)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9046)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9053)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9060)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9067)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9074)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9081)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9088)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9095)
        exp_stack.append(exp_caller_info)
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
                                     line_num=9122)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9131)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9140)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9153)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9160)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9167)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9174)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9181)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9188)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9195)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9203)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9210)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9217)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9224)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9231)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9238)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9245)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9252)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9259)
        exp_stack.append(exp_caller_info)
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
                                     line_num=9297)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9306)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9315)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9328)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9335)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9342)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9349)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9356)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9363)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9370)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9378)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9385)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9392)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9399)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9406)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9413)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9420)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9427)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9434)
        exp_stack.append(exp_caller_info)
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
                                     line_num=9460)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9469)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9478)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9491)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9498)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9505)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9512)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9519)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9526)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9533)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9541)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9548)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9555)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9562)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9569)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9576)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9583)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9590)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9597)
        exp_stack.append(exp_caller_info)
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
                                     line_num=9624)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9633)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9642)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9655)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9662)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9669)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9676)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9683)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9690)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9697)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9705)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9712)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9719)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9726)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9733)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9740)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9747)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9754)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9761)
        exp_stack.append(exp_caller_info)
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
                                     line_num=9787)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9796)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9805)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9818)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9825)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9832)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9839)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9846)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9853)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9860)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9868)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9875)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9882)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9889)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9896)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9903)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9910)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9917)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9924)
        exp_stack.append(exp_caller_info)
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
                                     line_num=9950)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9959)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9968)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9981)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9988)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9995)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10002)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10009)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10016)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10023)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10031)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10038)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10045)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10052)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10059)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10066)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10073)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10080)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10087)
        exp_stack.append(exp_caller_info)
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
                                     line_num=10114)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10123)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10132)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10145)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10152)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10159)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10166)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10173)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10180)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10187)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10195)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10202)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10209)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10216)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10223)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10230)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10237)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10244)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10251)
        exp_stack.append(exp_caller_info)
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
                                     line_num=10277)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10286)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10295)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10308)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10313)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10319)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10326)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10330)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10334)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10339)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10346)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10350)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10355)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10362)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10369)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10376)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10383)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10390)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10397)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10404)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10412)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10419)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10426)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10433)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10440)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10447)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10454)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10461)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10468)
        exp_stack.append(exp_caller_info)
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
                                     line_num=10494)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10503)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10512)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10526)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10532)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10539)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10544)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10551)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10556)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10563)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10570)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10577)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10584)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10591)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10598)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10605)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10613)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10620)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10627)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10634)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10641)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10648)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10655)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10662)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10669)
        exp_stack.append(exp_caller_info)
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
                                     line_num=10696)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10705)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10714)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10728)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10734)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10741)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s2bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10746)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10750)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10755)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10762)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10766)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10770)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10775)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10782)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10789)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10796)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10803)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10810)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10817)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10824)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10832)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10839)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10846)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10853)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10860)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10867)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10874)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10881)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10888)
        exp_stack.append(exp_caller_info)
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
                                     line_num=10926)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10935)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10944)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=10976)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10985)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10994)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11026)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11035)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11044)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11076)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11085)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11094)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11126)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11135)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11144)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11177)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11186)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11195)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11228)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11237)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11246)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11278)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11287)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11296)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11329)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11338)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11347)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11391)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11400)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11409)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11441)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11450)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11459)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11492)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11501)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11510)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11542)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11551)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11560)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11592)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11601)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11610)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11643)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11652)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11661)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

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
                                     line_num=11693)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11702)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11711)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11724)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11729)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11735)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11742)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11746)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11750)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11755)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11762)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11766)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11771)
        exp_stack.append(exp_caller_info)
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
                                     line_num=11797)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11806)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11815)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11829)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11835)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11842)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11847)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11854)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11859)
        exp_stack.append(exp_caller_info)
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
                                     line_num=11886)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11895)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11904)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()

            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            capsys=capsys, file_arg='sys.stdout', 
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11918)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11924)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11931)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s3bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11936)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11940)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11945)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11952)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11956)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11960)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11965)
        exp_stack.append(exp_caller_info)
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
                              line_num=11988)

exp_stack0.append(exp_caller_info0)
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
exp_stack0.pop()
exp_caller_info0 = exp_caller_info0._replace(line_num=11999)
exp_stack0.append(exp_caller_info0)
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
exp_stack0.pop()
exp_caller_info0 = exp_caller_info0._replace(line_num=12018)
exp_stack0.append(exp_caller_info0)
func_get_caller_info_1(exp_stack=exp_stack0, capsys=None)

# call method
cls_get_caller_info01 = ClassGetCallerInfo1()
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12026)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_m1(exp_stack=exp_stack0, capsys=None)

# call static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12033)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_s1(exp_stack=exp_stack0, capsys=None)

# call class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12040)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack0, capsys=None)

# call overloaded base class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12047)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12054)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12061)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call subclass method
cls_get_caller_info01S = ClassGetCallerInfo1S()
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12069)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1s(exp_stack=exp_stack0, capsys=None)

# call subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12076)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1s(exp_stack=exp_stack0, capsys=None)

# call subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12083)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12090)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12097)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12104)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call base method from subclass method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12111)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1sb(exp_stack=exp_stack0, capsys=None)

# call base static method from subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12118)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1sb(exp_stack=exp_stack0, capsys=None)

# call base class method from subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=12125)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack0, capsys=None)
