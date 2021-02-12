"""test_diag_msg.py module."""

from datetime import datetime
# noinspection PyProtectedMember
from sys import _getframe
from typing import Any, cast, Deque, List, Optional, Union

import pytest
from collections import deque

from scottbrian_utils.diag_msg import get_caller_info
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.diag_msg import diag_msg
from scottbrian_utils.diag_msg import CallerInfo
from scottbrian_utils.diag_msg import diag_msg_datetime_fmt
from scottbrian_utils.diag_msg import get_formatted_call_seq_depth

depth_arg_list = [0, 1, 2, 3]


@pytest.fixture(params=depth_arg_list)  # type: ignore
def depth_arg(request: Any) -> int:
    """Using different depth args.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


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
        if i == depth - 1:
            break

    return exp_seq


###############################################################################
# verify_diag_msg is a helper function used by many test cases
###############################################################################
def verify_diag_msg(exp_stack: Deque[CallerInfo],
                    before_time: datetime,
                    after_time: datetime,
                    cap_msg: str,
                    exp_msg: List[Any],
                    depth: int = 0,
                    dt_format: str = diag_msg_datetime_fmt) -> None:
    """Verify the captured msg is as expected.

    Args:
        exp_stack: The expected stack of callers
        before_time: The time just before issuing the diag_msg
        after_time: The time just after the diag_msg
        cap_msg: The captured diag_msg
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
    if dt_format == '0':
        dt_format = diag_msg_datetime_fmt
    before_time = datetime.strptime(
        before_time.strftime(dt_format), dt_format)
    after_time = datetime.strptime(
        after_time.strftime(dt_format), dt_format)
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
            call_seq = f'{call_seq}{word}'
        elif word == '->':  # odd and we have arrow
            call_seq = f'{call_seq} {word} '
        else:  # odd and no arrow (beyond call sequence)
            str_list.insert(0, word)  # put it back
            break  # we are done

    if depth > 0:  # if caller wants to limit the depth
        call_seq = seq_slice(call_seq=call_seq, end=depth)

    assert call_seq == get_exp_seq(exp_stack=exp_stack, depth=depth)

    check_msg = []
    for word in exp_msg:
        check_msg.append(str(word))

    assert str_list == check_msg


###############################################################################
# verify_diag_msg is a helper function used by many test cases
###############################################################################
def verify_call_seq(exp_stack: Deque[CallerInfo],
                    call_seq: str,
                    seq_latest: Optional[int] = None,
                    seq_depth: int = 0) -> None:
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
    if seq_depth == 0:
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
                                     line_num=317)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence()

        verify_call_seq(exp_stack=exp_stack, call_seq=call_seq)

    ###########################################################################
    # Test with latest and depth parms with stack of 1
    ###########################################################################
    def test_get_call_seq_with_parms(self,
                                     latest_arg: int,
                                     depth_arg: int) -> None:
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
                                     line_num=343)
        exp_stack.append(exp_caller_info)
        call_seq = ''
        if latest_arg is None and depth_arg == 0:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg != 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=348)
            exp_stack.append(exp_caller_info)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg == 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=353)
            exp_stack.append(exp_caller_info)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg != 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=358)
            exp_stack.append(exp_caller_info)
            call_seq = get_formatted_call_sequence(latest=latest_arg,
                                                   depth=depth_arg)

        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_latest=latest_arg,
                        seq_depth=depth_arg)

        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=369)
        exp_stack.append(exp_caller_info)
        self.get_call_seq_depth_2(exp_stack=exp_stack,
                                  latest_arg=latest_arg,
                                  depth_arg=depth_arg)

    ###########################################################################
    # Test with latest and depth parms with stack of 2
    ###########################################################################
    def get_call_seq_depth_2(self,
                             exp_stack: Deque[CallerInfo],
                             latest_arg: int,
                             depth_arg: int) -> None:
        """Test get_formatted_call_seq at depth 2.

        Args:
            latest_arg: pytest fixture that specifies the how far back into the
                          stack to go for the most recent entry
            depth_arg: pytest fixture that specifies how many entries to get

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='get_call_seq_depth_2',
                                     line_num=395)
        exp_stack.append(exp_caller_info)
        call_seq = ''
        if latest_arg is None and depth_arg == 0:
            call_seq = get_formatted_call_sequence()
        elif latest_arg is None and depth_arg != 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=400)
            exp_stack.append(exp_caller_info)
            call_seq = get_formatted_call_sequence(depth=depth_arg)
        elif latest_arg is not None and depth_arg == 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=405)
            exp_stack.append(exp_caller_info)
            call_seq = get_formatted_call_sequence(latest=latest_arg)
        elif latest_arg is not None and depth_arg != 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=410)
            exp_stack.append(exp_caller_info)
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
                                     line_num=435)
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
                                     line_num=472)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg()
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        # exp_msg=['message', '0', '0'])
                        exp_msg=[],
                        depth=1)

    ###########################################################################
    # diag_msg with parms
    ###########################################################################
    def test_diag_msg_with_parms(self,
                                 capsys: pytest.CaptureFixture[str],
                                 dt_format_arg: str,
                                 depth_arg: int) -> None:
        """Test various combinations of msg_diag.

        Args:
            capsys: Pytest fixture that captures output
            dt_format_arg: Specifies the datetime format used for diag_msg
            depth_arg: The number of entries to build

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestDiagMsg',
                                     func_name='test_diag_msg_with_parms',
                                     line_num=506)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        if dt_format_arg == '0':
            diag_msg()
        else:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=511)
            exp_stack.append(exp_caller_info)
            diag_msg(dt_format=dt_format_arg)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        # exp_msg=['message', '0', '0'])
                        exp_msg=[],
                        depth=1,
                        dt_format=dt_format_arg)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=525)
        exp_stack.append(exp_caller_info)
        self.diag_msg_depth_2(exp_stack=exp_stack,
                              capsys=capsys,
                              dt_format_arg=dt_format_arg,
                              depth_arg=depth_arg)

    ###########################################################################
    # Depth 2 test
    ###########################################################################
    def diag_msg_depth_2(self,
                         exp_stack: Deque[CallerInfo],
                         capsys: pytest.CaptureFixture[str],
                         dt_format_arg: str,
                         depth_arg: int) -> None:
        """Test msg_diag with two callers in the sequence.

        Args:
            exp_stack: The expected stack as modified by each test case
            capsys: Pytest fixture that captures output
            dt_format_arg: Specifies the datetime format used for diag_msg
            depth_arg: The number of entries to build

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestDiagMsg',
                                     func_name='diag_msg_depth_2',
                                     line_num=554)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        if dt_format_arg == '0' and depth_arg == 0:
            diag_msg()
        elif dt_format_arg == '0' and depth_arg > 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=559)
            exp_stack.append(exp_caller_info)
            diag_msg(depth=depth_arg)
        elif dt_format_arg != '0' and depth_arg == 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=564)
            exp_stack.append(exp_caller_info)
            diag_msg(dt_format=dt_format_arg)
        else:  # both args non-zero
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=569)
            exp_stack.append(exp_caller_info)
            diag_msg(dt_format=dt_format_arg, depth=depth_arg)

        after_time = datetime.now()
        captured = capsys.readouterr().out
        # If depth is not specified then diag_msg will default to
        # a depth of 3. This routine, however, is only predictable at a
        # depth of 2. So, if the depth was defaulted (depth_arg of 0) or
        # diag_msg was specified with depth_arg of 3, we need to limit what
        # we verify to a depth of 2 which is what the following code will do.
        if depth_arg == 0 or depth_arg == 3:
            depth_to_verify = 2
        else:
            depth_to_verify = depth_arg  # allow verify to use 1 or 2
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        # exp_msg=['message', '0', '0'])
                        exp_msg=[],
                        depth=depth_to_verify,
                        dt_format=dt_format_arg)

        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=594)
        exp_stack.append(exp_caller_info)
        self.diag_msg_depth_3(exp_stack=exp_stack,
                              capsys=capsys,
                              dt_format_arg=dt_format_arg,
                              depth_arg=depth_arg)

        exp_stack.pop()  # return with correct stack

    ###########################################################################
    # Depth 3 test
    ###########################################################################
    def diag_msg_depth_3(self,
                         exp_stack: Deque[CallerInfo],
                         capsys: pytest.CaptureFixture[str],
                         dt_format_arg: str,
                         depth_arg: int) -> None:
        """Test msg_diag with three callers in the sequence.

        Args:
            exp_stack: The expected stack as modified by each test case
            capsys: Pytest fixture that captures output
            dt_format_arg: Specifies the datetime format used for diag_msg
            depth_arg: The number of entries to build

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestDiagMsg',
                                     func_name='diag_msg_depth_3',
                                     line_num=625)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        if dt_format_arg == '0' and depth_arg == 0:
            diag_msg()
        elif dt_format_arg == '0' and depth_arg > 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=630)
            exp_stack.append(exp_caller_info)
            diag_msg(depth=depth_arg)
        elif dt_format_arg != '0' and depth_arg == 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=635)
            exp_stack.append(exp_caller_info)
            diag_msg(dt_format=dt_format_arg)
        else:  # both args non-zero
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=640)
            exp_stack.append(exp_caller_info)
            diag_msg(dt_format=dt_format_arg, depth=depth_arg)

        after_time = datetime.now()
        captured = capsys.readouterr().out
        # If depth is not specified then diag_msg will default to
        # a depth of 3. Unlike diag_msg_depth_2, this routine, can handle a
        # depth of 3. So, if the depth was defaulted to 3 (depth_arg of 0)
        # or was specified at 3, we will verify to a depth of 3.
        if depth_arg == 0:
            depth_to_verify = 3
        else:
            depth_to_verify = depth_arg  # allow verify to use 1 or 2 or 3
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        # exp_msg=['message', '0', '0'])
                        exp_msg=[],
                        depth=depth_to_verify,
                        dt_format=dt_format_arg)

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
                                 line_num=692)
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
    exp_caller_info = exp_caller_info._replace(line_num=701)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=1)

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=710)
    exp_stack.append(exp_caller_info)
    before_time = datetime.now()
    diag_msg('message 0', 0, depth=1)
    after_time = datetime.now()
    captured = capsys.readouterr().out
    verify_diag_msg(exp_stack=exp_stack,
                    before_time=before_time,
                    after_time=after_time,
                    cap_msg=captured,
                    exp_msg=['message', '0', '0'])

    # call module level function
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=723)
    exp_stack.append(exp_caller_info)
    func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info1 = ClassGetCallerInfo1()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=730)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

    # call static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=736)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

    # call class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=742)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=748)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=755)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=762)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info1s = ClassGetCallerInfo1S()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=770)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=777)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=784)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=791)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=798)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=805)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=812)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=819)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=826)
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
                                 line_num=852)
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
    exp_caller_info = exp_caller_info._replace(line_num=861)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=871)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=len(exp_stack))
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

    # call module level function
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=884)
    exp_stack.append(exp_caller_info)
    func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info2 = ClassGetCallerInfo2()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=891)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

    # call static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=897)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

    # call class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=903)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=909)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=916)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=923)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info2s = ClassGetCallerInfo2S()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=931)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=938)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=945)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=952)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=959)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=966)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=973)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=980)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=987)
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
                                 line_num=1013)
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
    exp_caller_info = exp_caller_info._replace(line_num=1022)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1032)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 2', 2, depth=len(exp_stack))
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '2', '2'])

    # call module level function
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1045)
    exp_stack.append(exp_caller_info)
    func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info3 = ClassGetCallerInfo3()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1052)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

    # call static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1058)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

    # call class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1064)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1070)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1077)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1084)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info3s = ClassGetCallerInfo3S()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1092)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1099)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1106)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1113)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1120)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1127)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1134)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1141)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=1148)
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
                                 line_num=1174)
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
    exp_caller_info = exp_caller_info._replace(line_num=1183)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1193)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 2', 2, depth=len(exp_stack))
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
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
                                     line_num=1234)
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
        exp_caller_info = exp_caller_info._replace(line_num=1243)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1252)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1265)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1272)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1279)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1286)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1293)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1300)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1307)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1315)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1322)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1329)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1336)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1343)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1350)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1357)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1364)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1371)
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
                                     line_num=1394)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1398)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0(exp_stack=exp_stack,
                                                   capsys=capsys)

        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1404)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1408)
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
                                     line_num=1429)
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
        exp_caller_info = exp_caller_info._replace(line_num=1438)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1447)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=2)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1460)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1467)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1474)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1481)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1488)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1495)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1502)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1510)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1517)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1524)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1531)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1538)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1545)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1552)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1559)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1566)
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
                                     line_num=1591)
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
        exp_caller_info = exp_caller_info._replace(line_num=1600)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1609)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1622)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1629)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1636)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1643)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1650)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1657)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1664)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1672)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1679)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1686)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1693)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1700)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1707)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1714)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1721)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1728)
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
                                     line_num=1753)
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
        exp_caller_info = exp_caller_info._replace(line_num=1762)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1771)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1784)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1791)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1798)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1805)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1812)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1819)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1826)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1834)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1841)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1848)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1855)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1862)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1869)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1876)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1883)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1890)
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
                                     line_num=1915)
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
        exp_caller_info = exp_caller_info._replace(line_num=1924)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1933)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1946)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1953)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1960)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1967)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1974)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1981)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1988)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1996)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2003)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2010)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2017)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2024)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2031)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2038)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2045)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2052)
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
                                     line_num=2078)
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
        exp_caller_info = exp_caller_info._replace(line_num=2087)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2096)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2109)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2116)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2123)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2130)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2137)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2144)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2151)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2159)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2166)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2173)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2180)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2187)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2194)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2201)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2208)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2215)
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
                                     line_num=2240)
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
        exp_caller_info = exp_caller_info._replace(line_num=2249)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2258)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=len(exp_stack))
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2271)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2278)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2285)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2292)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2299)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2306)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2313)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2321)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2328)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2335)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2342)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2349)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2356)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2363)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2370)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2377)
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
                                     line_num=2403)
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
        exp_caller_info = exp_caller_info._replace(line_num=2412)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2421)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=len(exp_stack))
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2434)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2441)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2448)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2455)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2462)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2469)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2476)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2484)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2491)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2498)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2505)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2512)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2519)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2526)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2533)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2540)
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
                                     line_num=2570)
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
        exp_caller_info = exp_caller_info._replace(line_num=2579)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2588)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=len(exp_stack))
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2601)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2608)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2615)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2622)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2629)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2636)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2643)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2651)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2658)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2665)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2672)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2679)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2686)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2693)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2700)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2707)
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
                                     line_num=2738)
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
        exp_caller_info = exp_caller_info._replace(line_num=2747)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2756)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2769)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2776)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2783)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2790)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2797)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2804)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2811)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2819)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2826)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2833)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2840)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2847)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2854)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2861)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2868)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2875)
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
                                     line_num=2900)
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
        exp_caller_info = exp_caller_info._replace(line_num=2909)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2918)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2931)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2938)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2945)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2952)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2959)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2966)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2973)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2981)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2988)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2995)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3002)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3009)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3016)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3023)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3030)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3037)
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
                                     line_num=3063)
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
        exp_caller_info = exp_caller_info._replace(line_num=3072)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3081)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3094)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3101)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3108)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3115)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3122)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3129)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3136)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3144)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3151)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3158)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3165)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3172)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3179)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3186)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3193)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3200)
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
                                     line_num=3225)
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
        exp_caller_info = exp_caller_info._replace(line_num=3234)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3243)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3256)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3263)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3270)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3277)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3284)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3291)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3298)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3306)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3313)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3320)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3327)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3334)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3341)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3348)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3355)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3362)
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
                                     line_num=3387)
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
        exp_caller_info = exp_caller_info._replace(line_num=3396)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3405)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3418)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3425)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3432)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3439)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3446)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3453)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3460)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3468)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3475)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3482)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3489)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3496)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3503)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3510)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3517)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3524)
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
                                     line_num=3550)
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
        exp_caller_info = exp_caller_info._replace(line_num=3559)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3568)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3581)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3588)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3595)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3602)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3609)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3616)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3623)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3631)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3638)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3645)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3652)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3659)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3666)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3673)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3680)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3687)
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
                                     line_num=3712)
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
        exp_caller_info = exp_caller_info._replace(line_num=3721)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3730)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call base class normal method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3743)
        exp_stack.append(exp_caller_info)
        self.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3748)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3753)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3759)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3763)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3767)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3772)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3779)
        exp_stack.append(exp_caller_info)
        super().test_get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3783)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3788)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3795)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3802)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3809)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3816)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3823)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3830)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3837)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3845)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3852)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3859)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3866)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3873)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3880)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3887)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3894)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3901)
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
                                     line_num=3926)
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
        exp_caller_info = exp_caller_info._replace(line_num=3935)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3944)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call base class normal method target
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3958)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3963)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3969)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3974)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3981)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3986)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3993)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4000)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4007)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4014)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4021)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4028)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4035)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4043)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4050)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4057)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4064)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4071)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4078)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4085)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4092)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4099)
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
                                     line_num=4125)
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
        exp_caller_info = exp_caller_info._replace(line_num=4134)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4143)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        diag_msg('message 1', 1, depth=1)
        after_time = datetime.now()
        captured = capsys.readouterr().out
        verify_diag_msg(exp_stack=exp_stack,
                        before_time=before_time,
                        after_time=after_time,
                        cap_msg=captured,
                        exp_msg=['message', '1', '1'])

        # call base class normal method target
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4157)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4162)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4168)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s0bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4173)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4177)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4182)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)
        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4188)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4195)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4202)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4209)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4216)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4223)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4230)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4238)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4245)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4252)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4259)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4266)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4273)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4280)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4287)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4294)
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
                                     line_num=4332)
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
        exp_caller_info = exp_caller_info._replace(line_num=4341)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4350)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4363)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4370)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4377)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4384)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4391)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4398)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4405)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4413)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4420)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4427)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4434)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4441)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4448)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4455)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4462)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4469)
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
                                     line_num=4495)
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
        exp_caller_info = exp_caller_info._replace(line_num=4504)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4513)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4526)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4533)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4540)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4547)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4554)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4561)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4568)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4576)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4583)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4590)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4597)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4604)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4611)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4618)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4625)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4632)
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
                                     line_num=4658)
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
        exp_caller_info = exp_caller_info._replace(line_num=4667)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4676)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4689)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4696)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4703)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4710)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4717)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4724)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4731)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4739)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4746)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4753)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4760)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4767)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4774)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4781)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4788)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4795)
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
                                     line_num=4821)
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
        exp_caller_info = exp_caller_info._replace(line_num=4830)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4839)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4852)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4859)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4866)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4873)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4880)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4887)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4894)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4902)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4909)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4916)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4923)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4930)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4937)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4944)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4951)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4958)
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
                                     line_num=4984)
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
        exp_caller_info = exp_caller_info._replace(line_num=4993)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5002)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5015)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5022)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5029)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5036)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5043)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5050)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5057)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5065)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5072)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5079)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5086)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5093)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5100)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5107)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5114)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5121)
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
                                     line_num=5148)
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
        exp_caller_info = exp_caller_info._replace(line_num=5157)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5166)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5179)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5186)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5193)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5200)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5207)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5214)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5221)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5229)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5236)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5243)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5250)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5257)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5264)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5271)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5278)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5285)
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
                                     line_num=5312)
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
        exp_caller_info = exp_caller_info._replace(line_num=5321)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5330)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5343)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5350)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5357)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5364)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5371)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5378)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5385)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5393)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5400)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5407)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5414)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5421)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5428)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5435)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5442)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5449)
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
                                     line_num=5475)
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
        exp_caller_info = exp_caller_info._replace(line_num=5484)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5493)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5506)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5513)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5520)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5527)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5534)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5541)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5548)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5556)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5563)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5570)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5577)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5584)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5591)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5598)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5605)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5612)
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
                                     line_num=5639)
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
        exp_caller_info = exp_caller_info._replace(line_num=5648)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5657)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5670)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5677)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5684)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5691)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5698)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5705)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5712)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5720)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5727)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5734)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5741)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5748)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5755)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5762)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5769)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5776)
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
                                     line_num=5814)
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
        exp_caller_info = exp_caller_info._replace(line_num=5823)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5832)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5845)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5852)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5859)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5866)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5873)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5880)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5887)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5895)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5902)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5909)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5916)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5923)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5930)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5937)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5944)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5951)
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
                                     line_num=5977)
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
        exp_caller_info = exp_caller_info._replace(line_num=5986)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5995)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6008)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6015)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6022)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6029)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6036)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6043)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6050)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6058)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6065)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6072)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6079)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6086)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6093)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6100)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6107)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6114)
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
                                     line_num=6141)
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
        exp_caller_info = exp_caller_info._replace(line_num=6150)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6159)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6172)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6179)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6186)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6193)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6200)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6207)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6214)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6222)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6229)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6236)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6243)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6250)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6257)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6264)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6271)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6278)
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
                                     line_num=6304)
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
        exp_caller_info = exp_caller_info._replace(line_num=6313)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6322)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6335)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6342)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6349)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6356)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6363)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6370)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6377)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6385)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6392)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6399)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6406)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6413)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6420)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6427)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6434)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6441)
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
                                     line_num=6467)
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
        exp_caller_info = exp_caller_info._replace(line_num=6476)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6485)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6498)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6505)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6512)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6519)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6526)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6533)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6540)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6548)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6555)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6562)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6569)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6576)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6583)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6590)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6597)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6604)
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
                                     line_num=6631)
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
        exp_caller_info = exp_caller_info._replace(line_num=6640)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6649)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6662)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6669)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6676)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6683)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6690)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6697)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6704)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6712)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6719)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6726)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6733)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6740)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6747)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6754)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6761)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6768)
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
                                     line_num=6794)
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
        exp_caller_info = exp_caller_info._replace(line_num=6803)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6812)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6825)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6830)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6836)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6843)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6847)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6851)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6856)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6863)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6867)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6872)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6879)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6886)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6893)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6900)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6907)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6914)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6921)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6929)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6936)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6943)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6950)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6957)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6964)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6971)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6978)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6985)
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
                                     line_num=7011)
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
        exp_caller_info = exp_caller_info._replace(line_num=7020)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7029)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7043)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7049)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7056)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7061)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7068)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7073)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7080)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7087)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7094)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7101)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7108)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7115)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7122)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7130)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7137)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7144)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7151)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7158)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7165)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7172)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7179)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7186)
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
                                     line_num=7213)
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
        exp_caller_info = exp_caller_info._replace(line_num=7222)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7231)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7245)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7251)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7258)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s1bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7263)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7267)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7272)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7279)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7283)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7287)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7292)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7299)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7306)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7313)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7320)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7327)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7334)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7341)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7349)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7356)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7363)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7370)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7377)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7384)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7391)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7398)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7405)
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
                                     line_num=7443)
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
        exp_caller_info = exp_caller_info._replace(line_num=7452)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7461)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7474)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7481)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7488)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7495)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7502)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7509)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7516)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7524)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7531)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7538)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7545)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7552)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7559)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7566)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7573)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7580)
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
                                     line_num=7606)
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
        exp_caller_info = exp_caller_info._replace(line_num=7615)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7624)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7637)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7644)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7651)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7658)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7665)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7672)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7679)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7687)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7694)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7701)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7708)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7715)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7722)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7729)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7736)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7743)
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
                                     line_num=7769)
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
        exp_caller_info = exp_caller_info._replace(line_num=7778)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7787)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7800)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7807)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7814)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7821)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7828)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7835)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7842)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7850)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7857)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7864)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7871)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7878)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7885)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7892)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7899)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7906)
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
                                     line_num=7932)
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
        exp_caller_info = exp_caller_info._replace(line_num=7941)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7950)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7963)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7970)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7977)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7984)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7991)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7998)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8005)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8013)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8020)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8027)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8034)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8041)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8048)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8055)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8062)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8069)
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
                                     line_num=8095)
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
        exp_caller_info = exp_caller_info._replace(line_num=8104)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8113)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8126)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8133)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8140)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8147)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8154)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8161)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8168)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8176)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8183)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8190)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8197)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8204)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8211)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8218)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8225)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8232)
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
                                     line_num=8259)
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
        exp_caller_info = exp_caller_info._replace(line_num=8268)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8277)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8290)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8297)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8304)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8311)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8318)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8325)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8332)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8340)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8347)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8354)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8361)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8368)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8375)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8382)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8389)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8396)
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
                                     line_num=8423)
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
        exp_caller_info = exp_caller_info._replace(line_num=8432)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8441)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8454)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8461)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8468)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8475)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8482)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8489)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8496)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8504)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8511)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8518)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8525)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8532)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8539)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8546)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8553)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8560)
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
                                     line_num=8586)
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
        exp_caller_info = exp_caller_info._replace(line_num=8595)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8604)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8617)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8624)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8631)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8638)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8645)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8652)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8659)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8667)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8674)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8681)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8688)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8695)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8702)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8709)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8716)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8723)
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
                                     line_num=8750)
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
        exp_caller_info = exp_caller_info._replace(line_num=8759)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8768)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8781)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8788)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8795)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8802)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8809)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8816)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8823)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8831)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8838)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8845)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8852)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8859)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8866)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8873)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8880)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8887)
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
                                     line_num=8925)
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
        exp_caller_info = exp_caller_info._replace(line_num=8934)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8943)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8956)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8963)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8970)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8977)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8984)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8991)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8998)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9006)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9013)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9020)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9027)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9034)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9041)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9048)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9055)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9062)
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
                                     line_num=9088)
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
        exp_caller_info = exp_caller_info._replace(line_num=9097)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9106)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9119)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9126)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9133)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9140)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9147)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9154)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9161)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9169)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9176)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9183)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9190)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9197)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9204)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9211)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9218)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9225)
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
                                     line_num=9252)
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
        exp_caller_info = exp_caller_info._replace(line_num=9261)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9270)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9283)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9290)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9297)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9304)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9311)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9318)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9325)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9333)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9340)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9347)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9354)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9361)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9368)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9375)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9382)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9389)
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
                                     line_num=9415)
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
        exp_caller_info = exp_caller_info._replace(line_num=9424)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9433)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9446)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9453)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9460)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9467)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9474)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9481)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9488)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9496)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9503)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9510)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9517)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9524)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9531)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9538)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9545)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9552)
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
                                     line_num=9578)
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
        exp_caller_info = exp_caller_info._replace(line_num=9587)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9596)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9609)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9616)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9623)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9630)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9637)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9644)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9651)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9659)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9666)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9673)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9680)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9687)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9694)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9701)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9708)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9715)
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
                                     line_num=9742)
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
        exp_caller_info = exp_caller_info._replace(line_num=9751)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9760)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9773)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9780)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9787)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9794)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9801)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9808)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9815)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9823)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9830)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9837)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9844)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9851)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9858)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9865)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9872)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9879)
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
                                     line_num=9905)
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
        exp_caller_info = exp_caller_info._replace(line_num=9914)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9923)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9936)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9941)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9947)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9954)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9958)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9962)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9967)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9974)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9978)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9983)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9990)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9997)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10004)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10011)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10018)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10025)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10032)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10040)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10047)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10054)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10061)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10068)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10075)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10082)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10089)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10096)
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
                                     line_num=10122)
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
        exp_caller_info = exp_caller_info._replace(line_num=10131)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10140)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10154)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10160)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10167)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10172)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10179)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10184)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10191)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10198)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10205)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10212)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10219)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10226)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10233)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10241)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10248)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10255)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10262)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10269)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10276)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10283)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10290)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10297)
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
                                     line_num=10324)
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
        exp_caller_info = exp_caller_info._replace(line_num=10333)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10342)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10356)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10362)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10369)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s2bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10374)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10378)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10383)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10390)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10394)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10398)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10403)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10410)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10417)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10424)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10431)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10438)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10445)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10452)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10460)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10467)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10474)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10481)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10488)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10495)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10502)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10509)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10516)
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
                                     line_num=10554)
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
        exp_caller_info = exp_caller_info._replace(line_num=10563)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10572)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=10604)
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
        exp_caller_info = exp_caller_info._replace(line_num=10613)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10622)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=10654)
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
        exp_caller_info = exp_caller_info._replace(line_num=10663)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10672)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=10704)
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
        exp_caller_info = exp_caller_info._replace(line_num=10713)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10722)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=10754)
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
        exp_caller_info = exp_caller_info._replace(line_num=10763)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10772)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=10805)
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
        exp_caller_info = exp_caller_info._replace(line_num=10814)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10823)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=10856)
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
        exp_caller_info = exp_caller_info._replace(line_num=10865)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10874)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=10906)
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
        exp_caller_info = exp_caller_info._replace(line_num=10915)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10924)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=10957)
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
        exp_caller_info = exp_caller_info._replace(line_num=10966)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10975)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=11019)
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
        exp_caller_info = exp_caller_info._replace(line_num=11028)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11037)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=11069)
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
        exp_caller_info = exp_caller_info._replace(line_num=11078)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11087)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=11120)
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
        exp_caller_info = exp_caller_info._replace(line_num=11129)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11138)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=11170)
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
        exp_caller_info = exp_caller_info._replace(line_num=11179)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11188)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=11220)
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
        exp_caller_info = exp_caller_info._replace(line_num=11229)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11238)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=11271)
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
        exp_caller_info = exp_caller_info._replace(line_num=11280)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11289)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
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
                                     line_num=11321)
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
        exp_caller_info = exp_caller_info._replace(line_num=11330)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11339)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11352)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11357)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11363)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11370)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11374)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11378)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11383)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11390)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11394)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11399)
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
                                     line_num=11425)
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
        exp_caller_info = exp_caller_info._replace(line_num=11434)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11443)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11457)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11463)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11470)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11475)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11482)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11487)
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
                                     line_num=11514)
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
        exp_caller_info = exp_caller_info._replace(line_num=11523)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11532)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=len(exp_stack))
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call base class normal method target
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11546)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11552)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11559)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s3bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11564)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11568)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11573)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11580)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11584)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11588)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11593)
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
                              line_num=11616)

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
exp_caller_info0 = exp_caller_info0._replace(line_num=11627)
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
exp_caller_info0 = exp_caller_info0._replace(line_num=11646)
exp_stack0.append(exp_caller_info0)
func_get_caller_info_1(exp_stack=exp_stack0, capsys=None)

# call method
cls_get_caller_info01 = ClassGetCallerInfo1()
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11654)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_m1(exp_stack=exp_stack0, capsys=None)

# call static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11661)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_s1(exp_stack=exp_stack0, capsys=None)

# call class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11668)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack0, capsys=None)

# call overloaded base class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11675)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11682)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11689)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call subclass method
cls_get_caller_info01S = ClassGetCallerInfo1S()
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11697)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1s(exp_stack=exp_stack0, capsys=None)

# call subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11704)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1s(exp_stack=exp_stack0, capsys=None)

# call subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11711)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11718)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11725)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11732)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call base method from subclass method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11739)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1sb(exp_stack=exp_stack0, capsys=None)

# call base static method from subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11746)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1sb(exp_stack=exp_stack0, capsys=None)

# call base class method from subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11753)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack0, capsys=None)
