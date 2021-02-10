"""test_diag_msg.py module."""

from datetime import datetime
# noinspection PyProtectedMember
from sys import _getframe
from typing import Any, cast, Deque, List, Optional

import pytest
from collections import deque

from scottbrian_utils.diag_msg import get_caller_info
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.diag_msg import diag_msg
from scottbrian_utils.diag_msg import CallerInfo
from scottbrian_utils.diag_msg import diag_msg_datetime_fmt

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


###############################################################################
# trim_call_seq is used to reduce the depth of a call sequence string
###############################################################################
def trim_call_seq(call_seq: str,
                  depth: int) -> str:
    """Return a reduced depth call sequence string.

    Args:
        call_seq: The call sequence string to be reduced
        depth: The number of entries to reduce to

    Returns:
          The call string reduced
    """
    call_str_split_list = call_seq.split()
    ret_seq = ''
    for i, call_item in enumerate(reversed(call_str_split_list), 1):
        if i % 2 == 1:  # if i is odd, meaning we have a call item
            ret_seq = f'{call_item}{ret_seq}'
        else:  # i is even, meaning we have an arrow
            ret_seq = f' {call_item} {ret_seq}'

        if i == (2 * depth) - 1:  # if requested depth is accomplished
            break

    return ret_seq


###############################################################################
# get_exp_seq is a helper function used by many test cases
###############################################################################
def get_exp_seq(exp_stack: Deque[CallerInfo],
                depth: int = 0) -> str:
    """Return the expected call sequence string based on the exp_stack.

    Args:
        exp_stack: The expected stack as modified by each test case
        depth: The number of entries to build

    Returns:
          The call string that get_formatted_call_sequence is expected to
           return
    """
    if depth == 0:
        depth = len(exp_stack)
    exp_seq = ''
    arrow = ''
    for i, exp_info in enumerate(reversed(exp_stack), 1):
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
        if i == depth:
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
        call_seq = trim_call_seq(call_seq=call_seq, depth=depth)

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
                    seq_depth: int = 0,
                    stack_depth: int = 0
                    ) -> None:
    """Verify the captured msg is as expected.

    Args:
        exp_stack: The expected stack of callers
        call_seq: The call sequence from get_formatted_call_seq or from
                    diag_msg to check
        seq_depth: Specifies how many call entries to verify.
        stack_depth: The depth of the exp_stack to use.

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
    # in which case we can't use the entire exp_stack. Here is a summary of
    # the cases with the stack_depth and seq_depth specifications:
    # case 1: first test case adds itself to the exp_stack and then:
    #         a) calls get_formatted_call_seq with no depth specified, which
    #            defaults to a depth of 3:
    #                seq_depth: 1
    #                stack_depth: 0 (to allow full size stack of 1)
    #         b) calls get_formatted_call_seq with depth = 1 specified:
    #                seq_depth: 0 (to allow the full seq of 1)
    #                stack_depth: 0 (to allow full size stack of 1)
    #         c) calls get_formatted_call_seq with depth = 2 or more specified:
    #                seq_depth: 1 (to limit to what is known on the stack)
    #                stack_depth: 0 (to allow full size stack of 1)
    #
    # case 2: first test case function calls a second function which then
    #         a) calls get_formatted_call_seq with no depth specified, which
    #            defaults to a depth of 3:
    #                seq_depth: 2
    #                stack_depth: 0 (to allow full size stack of 2)
    #         b) calls get_formatted_call_seq with depth = 1 specified:
    #                seq_depth: 0 (to allow the full seq of 1)
    #                stack_depth: 1 (to limit to the call seq depth)
    #         c) calls get_formatted_call_seq with depth = 2 or more specified:
    #                seq_depth: 2 (to limit to what is known on the stack)
    #                stack_depth: 0 (to allow full size stack of 2)

    if seq_depth != 0:
        call_seq = trim_call_seq(call_seq=call_seq, depth=seq_depth)

    assert call_seq == get_exp_seq(exp_stack=exp_stack, depth=stack_depth)


###############################################################################
# Class to test get call sequence
###############################################################################
class TestCallSeq:
    """Class the test get_formatted_call_sequence."""
    def test_get_call_seq_basic(self):
        """Test basic get formatted call sequence function."""

        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestCallSeq',
                                     func_name='test_get_call_seq_basic',
                                     line_num=248)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence()

        verify_call_seq(exp_stack=exp_stack,
                        call_seq=call_seq,
                        seq_depth=1,
                        stack_depth=0)

    # def test_get_call_seq_full_stack(self):
    #     """Test to ensure we can run the entire stack."""
    #     prev_count = -1
    #     new_count = 0
    #     while prev_count  < new_count:
    #         get_formatted_call_sequence(latest: int = 0,
    #                                     depth: int = diag_msg_caller_depth) -> str:


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
                                     line_num=285)
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
                                     line_num=319)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        if dt_format_arg == '0':
            diag_msg()
        else:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=324)
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
        exp_caller_info = exp_caller_info._replace(line_num=338)
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
                                     line_num=367)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        if dt_format_arg == '0' and depth_arg == 0:
            diag_msg()
        elif dt_format_arg == '0' and depth_arg > 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=372)
            exp_stack.append(exp_caller_info)
            diag_msg(depth=depth_arg)
        elif dt_format_arg != '0' and depth_arg == 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=377)
            exp_stack.append(exp_caller_info)
            diag_msg(dt_format=dt_format_arg)
        else:  # both args non-zero
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=382)
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
        exp_caller_info = exp_caller_info._replace(line_num=407)
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
                                     line_num=438)
        exp_stack.append(exp_caller_info)
        before_time = datetime.now()
        if dt_format_arg == '0' and depth_arg == 0:
            diag_msg()
        elif dt_format_arg == '0' and depth_arg > 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=443)
            exp_stack.append(exp_caller_info)
            diag_msg(depth=depth_arg)
        elif dt_format_arg != '0' and depth_arg == 0:
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=448)
            exp_stack.append(exp_caller_info)
            diag_msg(dt_format=dt_format_arg)
        else:  # both args non-zero
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=453)
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
                                 line_num=505)
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
    exp_caller_info = exp_caller_info._replace(line_num=514)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=1)

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=523)
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
    exp_caller_info = exp_caller_info._replace(line_num=536)
    exp_stack.append(exp_caller_info)
    func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info1 = ClassGetCallerInfo1()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=543)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

    # call static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=549)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

    # call class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=555)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=561)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=568)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=575)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info1s = ClassGetCallerInfo1S()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=583)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=590)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=597)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=604)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=611)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=618)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=625)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=632)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=639)
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
                                 line_num=665)
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
    exp_caller_info = exp_caller_info._replace(line_num=674)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=684)
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
    exp_caller_info = exp_caller_info._replace(line_num=697)
    exp_stack.append(exp_caller_info)
    func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info2 = ClassGetCallerInfo2()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=704)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

    # call static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=710)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

    # call class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=716)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=722)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=729)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=736)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info2s = ClassGetCallerInfo2S()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=744)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=751)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=758)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=765)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=772)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=779)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=786)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=793)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=800)
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
                                 line_num=826)
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
    exp_caller_info = exp_caller_info._replace(line_num=835)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=845)
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
    exp_caller_info = exp_caller_info._replace(line_num=858)
    exp_stack.append(exp_caller_info)
    func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info3 = ClassGetCallerInfo3()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=865)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

    # call static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=871)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

    # call class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=877)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=883)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=890)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=897)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info3s = ClassGetCallerInfo3S()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=905)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=912)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=919)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=926)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=933)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=940)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=947)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=954)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=961)
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
                                 line_num=987)
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
    exp_caller_info = exp_caller_info._replace(line_num=996)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1006)
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
                                     line_num=1047)
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
        exp_caller_info = exp_caller_info._replace(line_num=1056)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1065)
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
        exp_caller_info = exp_caller_info._replace(line_num=1078)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1085)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1092)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1099)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1106)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1113)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1120)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1128)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1135)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1142)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1149)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1156)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1163)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1170)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1177)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1184)
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
                                     line_num=1207)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1211)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0(exp_stack=exp_stack,
                                                   capsys=capsys)

        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1217)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1221)
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
                                     line_num=1242)
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
        exp_caller_info = exp_caller_info._replace(line_num=1251)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1260)
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
        exp_caller_info = exp_caller_info._replace(line_num=1273)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1280)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1287)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1294)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1301)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1308)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1315)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1323)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1330)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1337)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1344)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1351)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1358)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1365)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1372)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1379)
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
                                     line_num=1404)
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
        exp_caller_info = exp_caller_info._replace(line_num=1413)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1422)
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
        exp_caller_info = exp_caller_info._replace(line_num=1435)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1442)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1449)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1456)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1463)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1470)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1477)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1485)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1492)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1499)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1506)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1513)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1520)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1527)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1534)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1541)
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
                                     line_num=1566)
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
        exp_caller_info = exp_caller_info._replace(line_num=1575)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1584)
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
        exp_caller_info = exp_caller_info._replace(line_num=1597)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1604)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1611)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1618)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1625)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1632)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1639)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1647)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1654)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1661)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1668)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1675)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1682)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1689)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1696)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1703)
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
                                     line_num=1728)
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
        exp_caller_info = exp_caller_info._replace(line_num=1737)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1746)
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
        exp_caller_info = exp_caller_info._replace(line_num=1759)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1766)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1773)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1780)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1787)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1794)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1801)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1809)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1816)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1823)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1830)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1837)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1844)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1851)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1858)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1865)
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
                                     line_num=1891)
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
        exp_caller_info = exp_caller_info._replace(line_num=1900)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1909)
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
        exp_caller_info = exp_caller_info._replace(line_num=1922)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1929)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1936)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1943)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1950)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1957)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1964)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1972)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1979)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1986)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1993)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2000)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2007)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2014)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2021)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2028)
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
                                     line_num=2053)
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
        exp_caller_info = exp_caller_info._replace(line_num=2062)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2071)
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
        exp_caller_info = exp_caller_info._replace(line_num=2084)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2091)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2098)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2105)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2112)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2119)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2126)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2134)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2141)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2148)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2155)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2162)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2169)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2176)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2183)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2190)
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
                                     line_num=2216)
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
        exp_caller_info = exp_caller_info._replace(line_num=2225)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2234)
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
        exp_caller_info = exp_caller_info._replace(line_num=2247)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2254)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2261)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2268)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2275)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2282)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2289)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2297)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2304)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2311)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2318)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2325)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2332)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2339)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2346)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2353)
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
                                     line_num=2383)
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
        exp_caller_info = exp_caller_info._replace(line_num=2392)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2401)
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
        exp_caller_info = exp_caller_info._replace(line_num=2414)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2421)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2428)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2435)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2442)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2449)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2456)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2464)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2471)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2478)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2485)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2492)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2499)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2506)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2513)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2520)
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
                                     line_num=2551)
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
        exp_caller_info = exp_caller_info._replace(line_num=2560)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2569)
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
        exp_caller_info = exp_caller_info._replace(line_num=2582)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2589)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2596)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2603)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2610)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2617)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2624)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2632)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2639)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2646)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2653)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2660)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2667)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2674)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2681)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2688)
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
                                     line_num=2713)
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
        exp_caller_info = exp_caller_info._replace(line_num=2722)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2731)
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
        exp_caller_info = exp_caller_info._replace(line_num=2744)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2751)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2758)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2765)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2772)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2779)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2786)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2794)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2801)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2808)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2815)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2822)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2829)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2836)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2843)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2850)
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
                                     line_num=2876)
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
        exp_caller_info = exp_caller_info._replace(line_num=2885)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2894)
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
        exp_caller_info = exp_caller_info._replace(line_num=2907)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2914)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2921)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2928)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2935)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2942)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2949)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2957)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2964)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2971)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2978)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2985)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2992)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2999)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3006)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3013)
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
                                     line_num=3038)
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
        exp_caller_info = exp_caller_info._replace(line_num=3047)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3056)
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
        exp_caller_info = exp_caller_info._replace(line_num=3069)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3076)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3083)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3090)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3097)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3104)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3111)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3119)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3126)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3133)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3140)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3147)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3154)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3161)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3168)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3175)
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
                                     line_num=3200)
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
        exp_caller_info = exp_caller_info._replace(line_num=3209)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3218)
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
        exp_caller_info = exp_caller_info._replace(line_num=3231)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3238)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3245)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3252)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3259)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3266)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3273)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3281)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3288)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3295)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3302)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3309)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3316)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3323)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3330)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3337)
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
                                     line_num=3363)
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
        exp_caller_info = exp_caller_info._replace(line_num=3372)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3381)
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
        exp_caller_info = exp_caller_info._replace(line_num=3394)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3401)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3408)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3415)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3422)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3429)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3436)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3444)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3451)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3458)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3465)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3472)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3479)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3486)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3493)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3500)
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
                                     line_num=3525)
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
        exp_caller_info = exp_caller_info._replace(line_num=3534)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3543)
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
        exp_caller_info = exp_caller_info._replace(line_num=3556)
        exp_stack.append(exp_caller_info)
        self.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3561)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3566)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3572)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3576)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3580)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3585)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3592)
        exp_stack.append(exp_caller_info)
        super().test_get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3596)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3601)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3608)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3615)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3622)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3629)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3636)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3643)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3650)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3658)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3665)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3672)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3679)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3686)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3693)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3700)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3707)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3714)
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
                                     line_num=3739)
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
        exp_caller_info = exp_caller_info._replace(line_num=3748)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3757)
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
        exp_caller_info = exp_caller_info._replace(line_num=3771)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3776)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3782)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3787)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3794)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3799)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3806)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3813)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3820)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3827)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3834)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3841)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3848)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3856)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3863)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3870)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3877)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3884)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3891)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3898)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3905)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3912)
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
                                     line_num=3938)
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
        exp_caller_info = exp_caller_info._replace(line_num=3947)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3956)
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
        exp_caller_info = exp_caller_info._replace(line_num=3970)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3975)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3981)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s0bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3986)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3990)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3995)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)
        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4001)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4008)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4015)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4022)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4029)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4036)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4043)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4051)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4058)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4065)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4072)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4079)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4086)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4093)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4100)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4107)
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
                                     line_num=4145)
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
        exp_caller_info = exp_caller_info._replace(line_num=4154)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4163)
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
        exp_caller_info = exp_caller_info._replace(line_num=4176)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4183)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4190)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4197)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4204)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4211)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4218)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4226)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4233)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4240)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4247)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4254)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4261)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4268)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4275)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4282)
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
                                     line_num=4308)
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
        exp_caller_info = exp_caller_info._replace(line_num=4317)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4326)
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
        exp_caller_info = exp_caller_info._replace(line_num=4339)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4346)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4353)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4360)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4367)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4374)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4381)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4389)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4396)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4403)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4410)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4417)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4424)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4431)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4438)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4445)
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
                                     line_num=4471)
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
        exp_caller_info = exp_caller_info._replace(line_num=4480)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4489)
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
        exp_caller_info = exp_caller_info._replace(line_num=4502)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4509)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4516)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4523)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4530)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4537)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4544)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4552)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4559)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4566)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4573)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4580)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4587)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4594)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4601)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4608)
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
                                     line_num=4634)
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
        exp_caller_info = exp_caller_info._replace(line_num=4643)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4652)
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
        exp_caller_info = exp_caller_info._replace(line_num=4665)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4672)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4679)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4686)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4693)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4700)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4707)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4715)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4722)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4729)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4736)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4743)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4750)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4757)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4764)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4771)
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
                                     line_num=4797)
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
        exp_caller_info = exp_caller_info._replace(line_num=4806)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4815)
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
        exp_caller_info = exp_caller_info._replace(line_num=4828)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4835)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4842)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4849)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4856)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4863)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4870)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4878)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4885)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4892)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4899)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4906)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4913)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4920)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4927)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4934)
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
                                     line_num=4961)
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
        exp_caller_info = exp_caller_info._replace(line_num=4970)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4979)
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
        exp_caller_info = exp_caller_info._replace(line_num=4992)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4999)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5006)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5013)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5020)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5027)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5034)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5042)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5049)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5056)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5063)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5070)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5077)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5084)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5091)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5098)
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
                                     line_num=5125)
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
        exp_caller_info = exp_caller_info._replace(line_num=5134)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5143)
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
        exp_caller_info = exp_caller_info._replace(line_num=5156)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5163)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5170)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5177)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5184)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5191)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5198)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5206)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5213)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5220)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5227)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5234)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5241)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5248)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5255)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5262)
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
                                     line_num=5288)
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
        exp_caller_info = exp_caller_info._replace(line_num=5297)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5306)
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
        exp_caller_info = exp_caller_info._replace(line_num=5319)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5326)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5333)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5340)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5347)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5354)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5361)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5369)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5376)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5383)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5390)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5397)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5404)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5411)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5418)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5425)
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
                                     line_num=5452)
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
        exp_caller_info = exp_caller_info._replace(line_num=5461)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5470)
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
        exp_caller_info = exp_caller_info._replace(line_num=5483)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5490)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5497)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5504)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5511)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5518)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5525)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5533)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5540)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5547)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5554)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5561)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5568)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5575)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5582)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5589)
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
                                     line_num=5627)
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
        exp_caller_info = exp_caller_info._replace(line_num=5636)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5645)
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
        exp_caller_info = exp_caller_info._replace(line_num=5658)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5665)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5672)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5679)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5686)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5693)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5700)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5708)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5715)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5722)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5729)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5736)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5743)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5750)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5757)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5764)
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
                                     line_num=5790)
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
        exp_caller_info = exp_caller_info._replace(line_num=5799)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5808)
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
        exp_caller_info = exp_caller_info._replace(line_num=5821)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5828)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5835)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5842)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5849)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5856)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5863)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5871)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5878)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5885)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5892)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5899)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5906)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5913)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5920)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5927)
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
                                     line_num=5954)
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
        exp_caller_info = exp_caller_info._replace(line_num=5963)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5972)
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
        exp_caller_info = exp_caller_info._replace(line_num=5985)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5992)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5999)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6006)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6013)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6020)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6027)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6035)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6042)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6049)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6056)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6063)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6070)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6077)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6084)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6091)
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
                                     line_num=6117)
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
        exp_caller_info = exp_caller_info._replace(line_num=6126)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6135)
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
        exp_caller_info = exp_caller_info._replace(line_num=6148)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6155)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6162)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6169)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6176)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6183)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6190)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6198)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6205)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6212)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6219)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6226)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6233)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6240)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6247)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6254)
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
                                     line_num=6280)
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
        exp_caller_info = exp_caller_info._replace(line_num=6289)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6298)
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
        exp_caller_info = exp_caller_info._replace(line_num=6311)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6318)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6325)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6332)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6339)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6346)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6353)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6361)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6368)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6375)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6382)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6389)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6396)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6403)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6410)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6417)
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
                                     line_num=6444)
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
        exp_caller_info = exp_caller_info._replace(line_num=6453)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6462)
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
        exp_caller_info = exp_caller_info._replace(line_num=6475)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6482)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6489)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6496)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6503)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6510)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6517)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6525)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6532)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6539)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6546)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6553)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6560)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6567)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6574)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6581)
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
                                     line_num=6607)
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
        exp_caller_info = exp_caller_info._replace(line_num=6616)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6625)
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
        exp_caller_info = exp_caller_info._replace(line_num=6638)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6643)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6649)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6656)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6660)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6664)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6669)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6676)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6680)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6685)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6692)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6699)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6706)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6713)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6720)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6727)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6734)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6742)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6749)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6756)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6763)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6770)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6777)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6784)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6791)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6798)
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
                                     line_num=6824)
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
        exp_caller_info = exp_caller_info._replace(line_num=6833)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6842)
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
        exp_caller_info = exp_caller_info._replace(line_num=6856)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6862)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6869)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6874)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6881)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6886)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6893)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6900)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6907)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6914)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6921)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6928)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6935)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6943)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6950)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6957)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6964)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6971)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6978)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6985)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6992)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6999)
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
                                     line_num=7026)
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
        exp_caller_info = exp_caller_info._replace(line_num=7035)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7044)
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
        exp_caller_info = exp_caller_info._replace(line_num=7058)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7064)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7071)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s1bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7076)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7080)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7085)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7092)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7096)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7100)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7105)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7112)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7119)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7126)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7133)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7140)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7147)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7154)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7162)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7169)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7176)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7183)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7190)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7197)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7204)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7211)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7218)
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
                                     line_num=7256)
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
        exp_caller_info = exp_caller_info._replace(line_num=7265)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7274)
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
        exp_caller_info = exp_caller_info._replace(line_num=7287)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7294)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7301)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7308)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7315)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7322)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7329)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7337)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7344)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7351)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7358)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7365)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7372)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7379)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7386)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7393)
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
                                     line_num=7419)
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
        exp_caller_info = exp_caller_info._replace(line_num=7428)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7437)
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
        exp_caller_info = exp_caller_info._replace(line_num=7450)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7457)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7464)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7471)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7478)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7485)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7492)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7500)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7507)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7514)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7521)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7528)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7535)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7542)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7549)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7556)
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
                                     line_num=7582)
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
        exp_caller_info = exp_caller_info._replace(line_num=7591)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7600)
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
        exp_caller_info = exp_caller_info._replace(line_num=7613)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7620)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7627)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7634)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7641)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7648)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7655)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7663)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7670)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7677)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7684)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7691)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7698)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7705)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7712)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7719)
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
                                     line_num=7745)
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
        exp_caller_info = exp_caller_info._replace(line_num=7754)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7763)
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
        exp_caller_info = exp_caller_info._replace(line_num=7776)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7783)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7790)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7797)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7804)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7811)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7818)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7826)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7833)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7840)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7847)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7854)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7861)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7868)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7875)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7882)
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
                                     line_num=7908)
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
        exp_caller_info = exp_caller_info._replace(line_num=7917)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7926)
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
        exp_caller_info = exp_caller_info._replace(line_num=7939)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7946)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7953)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7960)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7967)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7974)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7981)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7989)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7996)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8003)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8010)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8017)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8024)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8031)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8038)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8045)
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
                                     line_num=8072)
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
        exp_caller_info = exp_caller_info._replace(line_num=8081)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8090)
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
        exp_caller_info = exp_caller_info._replace(line_num=8103)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8110)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8117)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8124)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8131)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8138)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8145)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8153)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8160)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8167)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8174)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8181)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8188)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8195)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8202)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8209)
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
                                     line_num=8236)
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
        exp_caller_info = exp_caller_info._replace(line_num=8245)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8254)
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
        exp_caller_info = exp_caller_info._replace(line_num=8267)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8274)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8281)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8288)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8295)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8302)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8309)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8317)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8324)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8331)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8338)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8345)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8352)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8359)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8366)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8373)
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
                                     line_num=8399)
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
        exp_caller_info = exp_caller_info._replace(line_num=8408)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8417)
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
        exp_caller_info = exp_caller_info._replace(line_num=8430)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8437)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8444)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8451)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8458)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8465)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8472)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8480)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8487)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8494)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8501)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8508)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8515)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8522)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8529)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8536)
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
                                     line_num=8563)
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
        exp_caller_info = exp_caller_info._replace(line_num=8572)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8581)
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
        exp_caller_info = exp_caller_info._replace(line_num=8594)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8601)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8608)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8615)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8622)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8629)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8636)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8644)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8651)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8658)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8665)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8672)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8679)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8686)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8693)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8700)
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
                                     line_num=8738)
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
        exp_caller_info = exp_caller_info._replace(line_num=8747)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8756)
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
        exp_caller_info = exp_caller_info._replace(line_num=8769)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8776)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8783)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8790)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8797)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8804)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8811)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8819)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8826)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8833)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8840)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8847)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8854)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8861)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8868)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8875)
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
                                     line_num=8901)
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
        exp_caller_info = exp_caller_info._replace(line_num=8910)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8919)
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
        exp_caller_info = exp_caller_info._replace(line_num=8932)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8939)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8946)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8953)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8960)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8967)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8974)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8982)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8989)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8996)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9003)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9010)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9017)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9024)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9031)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9038)
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
                                     line_num=9065)
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
        exp_caller_info = exp_caller_info._replace(line_num=9074)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9083)
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
        exp_caller_info = exp_caller_info._replace(line_num=9096)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9103)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9110)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9117)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9124)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9131)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9138)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9146)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9153)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9160)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9167)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9174)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9181)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9188)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9195)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9202)
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
                                     line_num=9228)
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
        exp_caller_info = exp_caller_info._replace(line_num=9237)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9246)
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
        exp_caller_info = exp_caller_info._replace(line_num=9259)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9266)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9273)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9280)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9287)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9294)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9301)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9309)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9316)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9323)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9330)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9337)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9344)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9351)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9358)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9365)
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
                                     line_num=9391)
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
        exp_caller_info = exp_caller_info._replace(line_num=9400)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9409)
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
        exp_caller_info = exp_caller_info._replace(line_num=9422)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9429)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9436)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9443)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9450)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9457)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9464)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9472)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9479)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9486)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9493)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9500)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9507)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9514)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9521)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9528)
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
                                     line_num=9555)
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
        exp_caller_info = exp_caller_info._replace(line_num=9564)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9573)
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
        exp_caller_info = exp_caller_info._replace(line_num=9586)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9593)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9600)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9607)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9614)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9621)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9628)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9636)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9643)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9650)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9657)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9664)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9671)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9678)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9685)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9692)
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
                                     line_num=9718)
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
        exp_caller_info = exp_caller_info._replace(line_num=9727)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9736)
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
        exp_caller_info = exp_caller_info._replace(line_num=9749)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9754)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9760)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9767)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9771)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9775)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9780)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9787)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9791)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9796)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9803)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9810)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9817)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9824)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9831)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9838)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9845)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9853)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9860)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9867)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9874)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9881)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9888)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9895)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9902)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9909)
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
                                     line_num=9935)
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
        exp_caller_info = exp_caller_info._replace(line_num=9944)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9953)
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
        exp_caller_info = exp_caller_info._replace(line_num=9967)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9973)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9980)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9985)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9992)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9997)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10004)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10011)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10018)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10025)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10032)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10039)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10046)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10054)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10061)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10068)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10075)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10082)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10089)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10096)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10103)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10110)
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
                                     line_num=10137)
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
        exp_caller_info = exp_caller_info._replace(line_num=10146)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10155)
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
        exp_caller_info = exp_caller_info._replace(line_num=10169)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10175)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10182)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s2bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10187)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10191)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10196)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10203)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10207)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10211)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10216)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10223)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10230)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10237)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10244)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10251)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10258)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10265)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10273)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10280)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10287)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10294)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10301)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10308)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10315)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10322)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10329)
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
                                     line_num=10367)
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
        exp_caller_info = exp_caller_info._replace(line_num=10376)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10385)
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
                                     line_num=10417)
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
        exp_caller_info = exp_caller_info._replace(line_num=10426)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10435)
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
                                     line_num=10467)
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
        exp_caller_info = exp_caller_info._replace(line_num=10476)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10485)
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
                                     line_num=10517)
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
        exp_caller_info = exp_caller_info._replace(line_num=10526)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10535)
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
                                     line_num=10567)
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
        exp_caller_info = exp_caller_info._replace(line_num=10576)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10585)
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
                                     line_num=10618)
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
        exp_caller_info = exp_caller_info._replace(line_num=10627)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10636)
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
                                     line_num=10669)
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
        exp_caller_info = exp_caller_info._replace(line_num=10678)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10687)
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
                                     line_num=10719)
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
        exp_caller_info = exp_caller_info._replace(line_num=10728)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10737)
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
                                     line_num=10770)
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
        exp_caller_info = exp_caller_info._replace(line_num=10779)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10788)
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
                                     line_num=10832)
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
        exp_caller_info = exp_caller_info._replace(line_num=10841)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10850)
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
                                     line_num=10882)
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
        exp_caller_info = exp_caller_info._replace(line_num=10891)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10900)
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
                                     line_num=10933)
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
        exp_caller_info = exp_caller_info._replace(line_num=10942)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10951)
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
                                     line_num=10983)
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
        exp_caller_info = exp_caller_info._replace(line_num=10992)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11001)
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
                                     line_num=11033)
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
        exp_caller_info = exp_caller_info._replace(line_num=11042)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11051)
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
                                     line_num=11084)
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
        exp_caller_info = exp_caller_info._replace(line_num=11093)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11102)
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
                                     line_num=11134)
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
        exp_caller_info = exp_caller_info._replace(line_num=11143)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11152)
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
        exp_caller_info = exp_caller_info._replace(line_num=11165)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11170)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11176)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11183)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11187)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11191)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11196)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11203)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11207)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11212)
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
                                     line_num=11238)
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
        exp_caller_info = exp_caller_info._replace(line_num=11247)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11256)
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
        exp_caller_info = exp_caller_info._replace(line_num=11270)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11276)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11283)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11288)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11295)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11300)
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
                                     line_num=11327)
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
        exp_caller_info = exp_caller_info._replace(line_num=11336)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=11345)
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
        exp_caller_info = exp_caller_info._replace(line_num=11359)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11365)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11372)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s3bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11377)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11381)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11386)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11393)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11397)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11401)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11406)
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
                              line_num=11429)

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
exp_caller_info0 = exp_caller_info0._replace(line_num=11440)
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
exp_caller_info0 = exp_caller_info0._replace(line_num=11459)
exp_stack0.append(exp_caller_info0)
func_get_caller_info_1(exp_stack=exp_stack0, capsys=None)

# call method
cls_get_caller_info01 = ClassGetCallerInfo1()
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11467)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_m1(exp_stack=exp_stack0, capsys=None)

# call static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11474)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_s1(exp_stack=exp_stack0, capsys=None)

# call class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11481)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack0, capsys=None)

# call overloaded base class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11488)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11495)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11502)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call subclass method
cls_get_caller_info01S = ClassGetCallerInfo1S()
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11510)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1s(exp_stack=exp_stack0, capsys=None)

# call subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11517)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1s(exp_stack=exp_stack0, capsys=None)

# call subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11524)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11531)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11538)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11545)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call base method from subclass method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11552)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1sb(exp_stack=exp_stack0, capsys=None)

# call base static method from subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11559)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1sb(exp_stack=exp_stack0, capsys=None)

# call base class method from subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11566)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack0, capsys=None)
