"""test_diag_msg.py module."""

from datetime import datetime
# noinspection PyProtectedMember
from sys import _getframe
from typing import Any, Deque, List, Optional

import pytest
from collections import deque

from scottbrian_utils.diag_msg import get_caller_info
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.diag_msg import diag_msg
from scottbrian_utils.diag_msg import CallerInfo
from scottbrian_utils.diag_msg import diag_msg_datetime_fmt


###############################################################################
# get_exp_seq is a helper function used by many test cases
###############################################################################
def get_exp_seq(exp_stack: Deque[CallerInfo]) -> str:
    """Return the expected call sequence string.

    Args:
        exp_stack: The expected stack as modified by each test case

    Returns:
          The call string that get_formatted_call_sequence is expected to
           return
    """
    exp_seq = ''
    arrow = ' -> '
    for i, exp_info in enumerate(exp_stack):
        if i == len(exp_stack) - 1:
            arrow = ''
        exp_seq = f'{exp_seq}{exp_info.mod_name}'
        if exp_info.func_name:
            exp_seq = f'{exp_seq}::'
            if exp_info.cls_name:
                exp_seq = f'{exp_seq}{exp_info.cls_name}.'
            exp_seq = f'{exp_seq}{exp_info.func_name}'
        exp_seq = f'{exp_seq}:{exp_info.line_num}{arrow}'

    return exp_seq


###############################################################################
# verify_diag_msg is a helper function used by many test cases
###############################################################################
def verify_diag_msg(exp_stack: Deque[CallerInfo],
                    before_time: datetime,
                    after_time: datetime,
                    cap_msg: str,
                    exp_msg: List[Any]) -> None:
    """Verify the captured msg is as expected

    Args:
        exp_stack: The expected stack of callers
        before_time: The time just before issuing the diag_msg
        after_time: The time just after the diag_msg
        cap_msg: The captured diag_msg
        exp_msg: A list of the expected message parts

    """
    before_time = datetime.strptime(
        before_time.strftime(diag_msg_datetime_fmt), diag_msg_datetime_fmt)
    after_time = datetime.strptime(
        after_time.strftime(diag_msg_datetime_fmt), diag_msg_datetime_fmt)
    str_list = cap_msg.split()
    msg_time = datetime.strptime(str_list.pop(0), diag_msg_datetime_fmt)
    assert before_time < msg_time < after_time

    # build the expected call sequence string
    actual_call_seq = ''
    for i in range(len(str_list)):
        word = str_list.pop(0)
        if i % 2 == 0:  # if even
            actual_call_seq = f'{actual_call_seq}{word}'
        elif word == '->':  # odd and we have arrow
            actual_call_seq = f'{actual_call_seq} {word} '
        else:  # off and no arrow
            str_list.insert(0, word)  # put it back
            break  # we are done
    assert actual_call_seq == get_exp_seq(exp_stack=exp_stack)

    check_msg = []
    for word in exp_msg:
        check_msg.append(str(word))

    assert str_list == check_msg


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
def test_func_get_caller_info_0(capsys: Any) -> None:
    """Module level function 0 to test get_caller_info.

    Args:
        capsys: Pytest fixture that captures output
    """
    exp_stack: Deque[CallerInfo] = deque()
    exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                 cls_name='',
                                 func_name='test_func_get_caller_info_0',
                                 line_num=121)
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
    exp_caller_info = exp_caller_info._replace(line_num=130)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=1)

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=139)
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
    exp_caller_info = exp_caller_info._replace(line_num=152)
    exp_stack.append(exp_caller_info)
    func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info1 = ClassGetCallerInfo1()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=159)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack, capsys=capsys)

    # call static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=165)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack, capsys=capsys)

    # call class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=171)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=177)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=184)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=191)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info1s = ClassGetCallerInfo1S()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=199)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=206)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=213)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=220)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=227)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=234)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=241)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=248)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=255)
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
                                 line_num=281)
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
    exp_caller_info = exp_caller_info._replace(line_num=290)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=300)
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
    exp_caller_info = exp_caller_info._replace(line_num=313)
    exp_stack.append(exp_caller_info)
    func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info2 = ClassGetCallerInfo2()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=320)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack, capsys=capsys)

    # call static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=326)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack, capsys=capsys)

    # call class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=332)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=338)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=345)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=352)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info2s = ClassGetCallerInfo2S()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=360)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=367)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=374)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=381)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=388)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=395)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=402)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=409)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=416)
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
                                 line_num=442)
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
    exp_caller_info = exp_caller_info._replace(line_num=451)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=461)
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
    exp_caller_info = exp_caller_info._replace(line_num=474)
    exp_stack.append(exp_caller_info)
    func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

    # call method
    cls_get_caller_info3 = ClassGetCallerInfo3()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=481)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack, capsys=capsys)

    # call static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=487)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack, capsys=capsys)

    # call class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=493)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack, capsys=capsys)

    # call overloaded base class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=499)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=506)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call overloaded base class class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=513)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                             capsys=capsys)

    # call subclass method
    cls_get_caller_info3s = ClassGetCallerInfo3S()
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=521)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=528)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                              capsys=capsys)

    # call subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=535)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                             capsys=capsys)

    # call overloaded subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=542)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=549)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                               capsys=capsys)

    # call overloaded subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=556)
    exp_stack.append(exp_caller_info)
    ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                              capsys=capsys)

    # call base method from subclass method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=563)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base static method from subclass static method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=570)
    exp_stack.append(exp_caller_info)
    cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                               capsys=capsys)

    # call base class method from subclass class method
    exp_stack.pop()
    exp_caller_info = exp_caller_info._replace(line_num=577)
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
                                 line_num=603)
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
    exp_caller_info = exp_caller_info._replace(line_num=612)
    exp_stack.append(exp_caller_info)
    call_seq = get_formatted_call_sequence(depth=len(exp_stack))

    assert call_seq == get_exp_seq(exp_stack=exp_stack)

    # test diag_msg
    if capsys:  # if capsys, test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=622)
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
                                     line_num=663)
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
        exp_caller_info = exp_caller_info._replace(line_num=672)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=681)
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
        exp_caller_info = exp_caller_info._replace(line_num=694)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=701)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=708)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=715)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=722)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=729)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=736)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=744)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=751)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=758)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=765)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=772)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=779)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=786)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=793)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=800)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 2
    ###########################################################################
    def test_get_caller_info_helper(self, capsys: Any):
        """Get capsys for static methods

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_helper',
                                     line_num=821)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s0(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=825)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0(exp_stack=exp_stack,
                                                   capsys=capsys)

        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=831)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=835)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)

    @staticmethod
    def get_caller_info_s0(exp_stack: Deque[CallerInfo],
                           capsys: Any) -> None:
        """Get caller info static method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='get_caller_info_s0',
                                     line_num=855)
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
        exp_caller_info = exp_caller_info._replace(line_num=864)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=873)
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
        exp_caller_info = exp_caller_info._replace(line_num=886)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=893)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=900)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=907)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=914)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=921)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=928)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=936)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=943)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=950)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=957)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=964)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=971)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=978)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=985)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=992)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 3
    ###########################################################################
    @classmethod
    def test_get_caller_info_c0(cls,
                                capsys: Any) -> None:
        """Get caller info class method 0.

        Args:
            capsys: Pytest fixture that captures output
        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_c0',
                                     line_num=1017)
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
        exp_caller_info = exp_caller_info._replace(line_num=1026)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1035)
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
        exp_caller_info = exp_caller_info._replace(line_num=1048)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1055)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1062)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1069)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1076)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1083)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1090)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1098)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1105)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1112)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1119)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1126)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1133)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1140)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1147)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1154)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 4
    ###########################################################################
    def test_get_caller_info_m0bo(self,
                                  capsys: Any) -> None:
        """Get caller info overloaded method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_m0bo',
                                     line_num=1179)
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
        exp_caller_info = exp_caller_info._replace(line_num=1188)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1197)
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
        exp_caller_info = exp_caller_info._replace(line_num=1210)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1217)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1224)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1231)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1238)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1245)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1252)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1260)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1267)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1274)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1281)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1288)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1295)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1302)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1309)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1316)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 5
    ###########################################################################
    @staticmethod
    def test_get_caller_info_s0bo(capsys: Any) -> None:
        """Get caller info overloaded static method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_s0bo',
                                     line_num=1341)
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
        exp_caller_info = exp_caller_info._replace(line_num=1350)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1359)
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
        exp_caller_info = exp_caller_info._replace(line_num=1372)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1379)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1386)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1393)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1400)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1407)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1414)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1422)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1429)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1436)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1443)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1450)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1457)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1464)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1471)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1478)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 6
    ###########################################################################
    @classmethod
    def test_get_caller_info_c0bo(cls,
                                  capsys: Any) -> None:
        """Get caller info overloaded class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_c0bo',
                                     line_num=1504)
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
        exp_caller_info = exp_caller_info._replace(line_num=1513)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1522)
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
        exp_caller_info = exp_caller_info._replace(line_num=1535)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1542)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1549)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1556)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1563)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1570)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1577)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1585)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1592)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1599)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1606)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1613)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1620)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1627)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1634)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1641)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 7
    ###########################################################################
    def test_get_caller_info_m0bt(self,
                                  capsys: Any) -> None:
        """Get caller info overloaded method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_m0bt',
                                     line_num=1666)
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
        exp_caller_info = exp_caller_info._replace(line_num=1675)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1684)
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
        exp_caller_info = exp_caller_info._replace(line_num=1697)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1704)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1711)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1718)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1725)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1732)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1739)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1747)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1754)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1761)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1768)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1775)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1782)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1789)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1796)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1803)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0 Method 8
    ###########################################################################
    @staticmethod
    def get_caller_info_s0bt(exp_stack: Deque[CallerInfo],
                             capsys: Any) -> None:
        """Get caller info overloaded static method 0.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='get_caller_info_s0bt',
                                     line_num=1829)
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
        exp_caller_info = exp_caller_info._replace(line_num=1838)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1847)
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
        exp_caller_info = exp_caller_info._replace(line_num=1860)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1867)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1874)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1881)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1888)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1895)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1902)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1910)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1917)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1924)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1931)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1938)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1945)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1952)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1959)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1966)
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
                                  capsys: Any) -> None:
        """Get caller info overloaded class method 0.

        Args:
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        if not exp_stack:
            exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='test_get_caller_info_c0bt',
                                     line_num=1995)
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
        exp_caller_info = exp_caller_info._replace(line_num=2004)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2013)
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
        exp_caller_info = exp_caller_info._replace(line_num=2026)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2033)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2040)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2047)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2054)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2061)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2068)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2076)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2083)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2090)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2097)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2104)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2111)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2118)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2125)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2132)
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
                                 capsys: Any) -> None:
        """Get caller info method 0.

        Args:
            capsys: Pytest fixture that captures output
        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_m0s',
                                     line_num=2163)
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
        exp_caller_info = exp_caller_info._replace(line_num=2172)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2181)
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
        exp_caller_info = exp_caller_info._replace(line_num=2194)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2201)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2208)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2215)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2222)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2229)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2236)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2244)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2251)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2258)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2265)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2272)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2279)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2286)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2293)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2300)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 2
    ###########################################################################
    @staticmethod
    def test_get_caller_info_s0s(capsys: Any) -> None:
        """Get caller info static method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_s0s',
                                     line_num=2325)
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
        exp_caller_info = exp_caller_info._replace(line_num=2334)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2343)
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
        exp_caller_info = exp_caller_info._replace(line_num=2356)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2363)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2370)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2377)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2384)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2391)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2398)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2406)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2413)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2420)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2427)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2434)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2441)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2448)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2455)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2462)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 3
    ###########################################################################
    @classmethod
    def test_get_caller_info_c0s(cls,
                                 capsys: Any) -> None:
        """Get caller info class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_c0s',
                                     line_num=2488)
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
        exp_caller_info = exp_caller_info._replace(line_num=2497)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2506)
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
        exp_caller_info = exp_caller_info._replace(line_num=2519)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2526)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2533)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2540)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2547)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2554)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2561)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2569)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2576)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2583)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2590)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2597)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2604)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2611)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2618)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2625)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 4
    ###########################################################################
    def test_get_caller_info_m0bo(self,
                                  capsys: Any) -> None:
        """Get caller info overloaded method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_m0bo',
                                     line_num=2650)
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
        exp_caller_info = exp_caller_info._replace(line_num=2659)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2668)
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
        exp_caller_info = exp_caller_info._replace(line_num=2681)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2688)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2695)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2702)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2709)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2716)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2723)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2731)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2738)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2745)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2752)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2759)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2766)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2773)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2780)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2787)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 5
    ###########################################################################
    @staticmethod
    def test_get_caller_info_s0bo(capsys: Any) -> None:
        """Get caller info overloaded static method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_s0bo',
                                     line_num=2812)
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
        exp_caller_info = exp_caller_info._replace(line_num=2821)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2830)
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
        exp_caller_info = exp_caller_info._replace(line_num=2843)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2850)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2857)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2864)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2871)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2878)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2885)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2893)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2900)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2907)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2914)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2921)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2928)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2935)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2942)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2949)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 6
    ###########################################################################
    @classmethod
    def test_get_caller_info_c0bo(cls,
                                  capsys: Any) -> None:
        """Get caller info overloaded class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_c0bo',
                                     line_num=2975)
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
        exp_caller_info = exp_caller_info._replace(line_num=2984)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2993)
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
        exp_caller_info = exp_caller_info._replace(line_num=3006)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3013)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3020)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3027)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3034)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3041)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3048)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3056)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3063)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3070)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3077)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3084)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3091)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3098)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3105)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3112)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 7
    ###########################################################################
    def test_get_caller_info_m0sb(self,
                                  capsys: Any) -> None:
        """Get caller info overloaded method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_m0sb',
                                     line_num=3137)
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
        exp_caller_info = exp_caller_info._replace(line_num=3146)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3155)
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
        exp_caller_info = exp_caller_info._replace(line_num=3168)
        exp_stack.append(exp_caller_info)
        self.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3173)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3178)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3184)
        exp_stack.append(exp_caller_info)
        self.test_get_caller_info_s0bt(capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3188)
        exp_stack.append(exp_caller_info)
        super().test_get_caller_info_s0bt(capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3192)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_s0bt(capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3196)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_s0bt(capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3202)
        exp_stack.append(exp_caller_info)
        super().test_get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3206)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3211)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3218)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3225)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3232)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3239)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3246)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3253)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3260)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3268)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3275)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3282)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3289)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3296)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3303)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3310)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3317)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3324)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 8
    ###########################################################################
    @staticmethod
    def test_get_caller_info_s0sb(capsys: Any) -> None:
        """Get caller info overloaded static method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_s0sb',
                                     line_num=3349)
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
        exp_caller_info = exp_caller_info._replace(line_num=3358)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3367)
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
        exp_caller_info = exp_caller_info._replace(line_num=3381)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3386)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3392)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_s0bt(capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3396)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_s0bt(capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3402)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3407)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3414)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3421)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3428)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3435)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3442)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3449)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3456)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3464)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3471)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3478)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3485)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3492)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3499)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3506)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3513)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3520)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()

    ###########################################################################
    # Class 0S Method 9
    ###########################################################################
    @classmethod
    def test_get_caller_info_c0sb(cls,
                                  capsys: Any) -> None:
        """Get caller info overloaded class method 0.

        Args:
            capsys: Pytest fixture that captures output

        """
        exp_stack: Deque[CallerInfo] = deque()
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0S',
                                     func_name='test_get_caller_info_c0sb',
                                     line_num=3546)
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
        exp_caller_info = exp_caller_info._replace(line_num=3555)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3564)
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
        exp_caller_info = exp_caller_info._replace(line_num=3578)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3583)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3589)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s0bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3594)
        exp_stack.append(exp_caller_info)
        super().test_get_caller_info_s0bt(capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3598)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_s0bt(capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3602)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_s0bt(capsys=capsys)
        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3607)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3614)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3621)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3628)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3635)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3642)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3649)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3657)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3664)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3671)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3678)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3685)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3692)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3699)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3706)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3713)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


###############################################################################
# Class 1
###############################################################################
class ClassGetCallerInfo1:
    """Class to get caller info1."""

    def __init__(self):
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
                                     line_num=3751)
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
        exp_caller_info = exp_caller_info._replace(line_num=3760)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=3769)
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
        exp_caller_info = exp_caller_info._replace(line_num=3782)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3789)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3796)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3803)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3810)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3817)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3824)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3832)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3839)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3846)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3853)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3860)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3867)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3874)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3881)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3888)
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
                                     line_num=3914)
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
        exp_caller_info = exp_caller_info._replace(line_num=3923)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=3932)
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
        exp_caller_info = exp_caller_info._replace(line_num=3945)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3952)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3959)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3966)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3973)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3980)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3987)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3995)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4002)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4009)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4016)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4023)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4030)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4037)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4044)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4051)
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
                                     line_num=4077)
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
        exp_caller_info = exp_caller_info._replace(line_num=4086)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4095)
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
        exp_caller_info = exp_caller_info._replace(line_num=4108)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4115)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4122)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4129)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4136)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4143)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4150)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4158)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4165)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4172)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4179)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4186)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4193)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4200)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4207)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4214)
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
                                     line_num=4240)
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
        exp_caller_info = exp_caller_info._replace(line_num=4249)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4258)
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
        exp_caller_info = exp_caller_info._replace(line_num=4271)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4278)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4285)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4292)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4299)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4306)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4313)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4321)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4328)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4335)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4342)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4349)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4356)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4363)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4370)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4377)
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
                                     line_num=4403)
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
        exp_caller_info = exp_caller_info._replace(line_num=4412)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4421)
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
        exp_caller_info = exp_caller_info._replace(line_num=4434)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4441)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4448)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4455)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4462)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4469)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4476)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4484)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4491)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4498)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4505)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4512)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4519)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4526)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4533)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4540)
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
                                     line_num=4567)
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
        exp_caller_info = exp_caller_info._replace(line_num=4576)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4585)
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
        exp_caller_info = exp_caller_info._replace(line_num=4598)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4605)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4612)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4619)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4626)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4633)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4640)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4648)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4655)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4662)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4669)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4676)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4683)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4690)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4697)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4704)
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
                                     line_num=4731)
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
        exp_caller_info = exp_caller_info._replace(line_num=4740)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=3)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4749)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=3)
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4762)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4769)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4776)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4783)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4790)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4797)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4804)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4812)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4819)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4826)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4833)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4840)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4847)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4854)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4861)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4868)
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
                                     line_num=4894)
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
        exp_caller_info = exp_caller_info._replace(line_num=4903)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=3)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4912)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=3)
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4925)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4932)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4939)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4946)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4953)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4960)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4967)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4975)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4982)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4989)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4996)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5003)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5010)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5017)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5024)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5031)
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
                                     line_num=5058)
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
        exp_caller_info = exp_caller_info._replace(line_num=5067)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=3)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5076)
            exp_stack.append(exp_caller_info)
            before_time = datetime.now()
            diag_msg('message 1', 1, depth=3)
            after_time = datetime.now()
            captured = capsys.readouterr().out
            verify_diag_msg(exp_stack=exp_stack,
                            before_time=before_time,
                            after_time=after_time,
                            cap_msg=captured,
                            exp_msg=['message', '1', '1'])

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5089)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5096)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5103)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5110)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5117)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5124)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5131)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5139)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5146)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5153)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5160)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5167)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5174)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5181)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5188)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5195)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


###############################################################################
# Class 1S
###############################################################################
class ClassGetCallerInfo1S(ClassGetCallerInfo1):
    """Subclass to get caller info1."""

    def __init__(self):
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
                                     line_num=5233)
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
        exp_caller_info = exp_caller_info._replace(line_num=5242)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5251)
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
        exp_caller_info = exp_caller_info._replace(line_num=5264)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5271)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5278)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5285)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5292)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5299)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5306)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5314)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5321)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5328)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5335)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5342)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5349)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5356)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5363)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5370)
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
                                     line_num=5396)
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
        exp_caller_info = exp_caller_info._replace(line_num=5405)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5414)
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
        exp_caller_info = exp_caller_info._replace(line_num=5427)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5434)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5441)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5448)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5455)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5462)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5469)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5477)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5484)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5491)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5498)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5505)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5512)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5519)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5526)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5533)
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
                                     line_num=5560)
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
        exp_caller_info = exp_caller_info._replace(line_num=5569)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5578)
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
        exp_caller_info = exp_caller_info._replace(line_num=5591)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5598)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5605)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5612)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5619)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5626)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5633)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5641)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5648)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5655)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5662)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5669)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5676)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5683)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5690)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5697)
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
                                     line_num=5723)
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
        exp_caller_info = exp_caller_info._replace(line_num=5732)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5741)
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
        exp_caller_info = exp_caller_info._replace(line_num=5754)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5761)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5768)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5775)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5782)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5789)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5796)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5804)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5811)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5818)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5825)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5832)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5839)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5846)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5853)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5860)
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
                                     line_num=5886)
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
        exp_caller_info = exp_caller_info._replace(line_num=5895)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5904)
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
        exp_caller_info = exp_caller_info._replace(line_num=5917)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5924)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5931)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5938)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5945)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5952)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5959)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5967)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5974)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5981)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5988)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5995)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6002)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6009)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6016)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6023)
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
                                     line_num=6050)
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
        exp_caller_info = exp_caller_info._replace(line_num=6059)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6068)
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
        exp_caller_info = exp_caller_info._replace(line_num=6081)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6088)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6095)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6102)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6109)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6116)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6123)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6131)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6138)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6145)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6152)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6159)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6166)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6173)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6180)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6187)
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
                                     line_num=6213)
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
        exp_caller_info = exp_caller_info._replace(line_num=6222)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6231)
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

        # call base class normal method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6244)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6249)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6255)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6262)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6266)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6270)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6275)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6282)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6286)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6291)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6298)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6305)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6312)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6319)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6326)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6333)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6340)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6348)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6355)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6362)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6369)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6376)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6383)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6390)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6397)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6404)
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
                                     line_num=6430)
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
        exp_caller_info = exp_caller_info._replace(line_num=6439)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6448)
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

        # call base class normal method target
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6462)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6468)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6475)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6480)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6487)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6492)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6499)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6506)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6513)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6520)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6527)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6534)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6541)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6549)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6556)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6563)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6570)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6577)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6584)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6591)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6598)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6605)
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
                                     line_num=6632)
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
        exp_caller_info = exp_caller_info._replace(line_num=6641)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6650)
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

        # call base class normal method target
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6664)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6670)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6677)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s1bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6682)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6686)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6691)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6698)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6702)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6706)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6711)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6718)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6725)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6732)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6739)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6746)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6753)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6760)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6768)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6775)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6782)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6789)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6796)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6803)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6810)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6817)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6824)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


###############################################################################
# Class 2
###############################################################################
class ClassGetCallerInfo2:
    """Class to get caller info2."""

    def __init__(self):
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
                                     line_num=6862)
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
        exp_caller_info = exp_caller_info._replace(line_num=6871)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6880)
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
        exp_caller_info = exp_caller_info._replace(line_num=6893)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6900)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6907)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6914)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6921)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6928)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6935)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6943)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6950)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6957)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6964)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6971)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6978)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6985)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6992)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6999)
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
                                     line_num=7025)
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
        exp_caller_info = exp_caller_info._replace(line_num=7034)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7043)
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
        exp_caller_info = exp_caller_info._replace(line_num=7056)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7063)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7070)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7077)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7084)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7091)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7098)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7106)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7113)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7120)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7127)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7134)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7141)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7148)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7155)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7162)
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
                                     line_num=7188)
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
        exp_caller_info = exp_caller_info._replace(line_num=7197)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7206)
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
        exp_caller_info = exp_caller_info._replace(line_num=7219)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7226)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7233)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7240)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7247)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7254)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7261)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7269)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7276)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7283)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7290)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7297)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7304)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7311)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7318)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7325)
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
                                     line_num=7351)
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
        exp_caller_info = exp_caller_info._replace(line_num=7360)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7369)
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
        exp_caller_info = exp_caller_info._replace(line_num=7382)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7389)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7396)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7403)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7410)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7417)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7424)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7432)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7439)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7446)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7453)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7460)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7467)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7474)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7481)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7488)
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
                                     line_num=7514)
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
        exp_caller_info = exp_caller_info._replace(line_num=7523)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7532)
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
        exp_caller_info = exp_caller_info._replace(line_num=7545)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7552)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7559)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7566)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7573)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7580)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7587)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7595)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7602)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7609)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7616)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7623)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7630)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7637)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7644)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7651)
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
                                     line_num=7678)
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
        exp_caller_info = exp_caller_info._replace(line_num=7687)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7696)
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
        exp_caller_info = exp_caller_info._replace(line_num=7709)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7716)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7723)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7730)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7737)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7744)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7751)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7759)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7766)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7773)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7780)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7787)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7794)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7801)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7808)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7815)
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
                                     line_num=7842)
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
        exp_caller_info = exp_caller_info._replace(line_num=7851)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7860)
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
        exp_caller_info = exp_caller_info._replace(line_num=7873)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7880)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7887)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7894)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7901)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7908)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7915)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7923)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7930)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7937)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7944)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7951)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7958)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7965)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7972)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7979)
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
                                     line_num=8005)
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
        exp_caller_info = exp_caller_info._replace(line_num=8014)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8023)
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
        exp_caller_info = exp_caller_info._replace(line_num=8036)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8043)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8050)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8057)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8064)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8071)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8078)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8086)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8093)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8100)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8107)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8114)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8121)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8128)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8135)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8142)
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
                                     line_num=8169)
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
        exp_caller_info = exp_caller_info._replace(line_num=8178)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8187)
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
        exp_caller_info = exp_caller_info._replace(line_num=8200)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8207)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8214)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8221)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8228)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8235)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8242)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8250)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8257)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8264)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8271)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8278)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8285)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8292)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8299)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8306)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


###############################################################################
# Class 2S
###############################################################################
class ClassGetCallerInfo2S(ClassGetCallerInfo2):
    """Subclass to get caller info2."""

    def __init__(self):
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
                                     line_num=8344)
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
        exp_caller_info = exp_caller_info._replace(line_num=8353)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8362)
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
        exp_caller_info = exp_caller_info._replace(line_num=8375)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8382)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8389)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8396)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8403)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8410)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8417)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8425)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8432)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8439)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8446)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8453)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8460)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8467)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8474)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8481)
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
                                     line_num=8507)
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
        exp_caller_info = exp_caller_info._replace(line_num=8516)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8525)
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
        exp_caller_info = exp_caller_info._replace(line_num=8538)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8545)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8552)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8559)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8566)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8573)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8580)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8588)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8595)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8602)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8609)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8616)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8623)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8630)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8637)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8644)
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
                                     line_num=8671)
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
        exp_caller_info = exp_caller_info._replace(line_num=8680)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8689)
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
        exp_caller_info = exp_caller_info._replace(line_num=8702)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8709)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8716)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8723)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8730)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8737)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8744)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8752)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8759)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8766)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8773)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8780)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8787)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8794)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8801)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8808)
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
                                     line_num=8834)
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
        exp_caller_info = exp_caller_info._replace(line_num=8843)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8852)
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
        exp_caller_info = exp_caller_info._replace(line_num=8865)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8872)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8879)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8886)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8893)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8900)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8907)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8915)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8922)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8929)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8936)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8943)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8950)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8957)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8964)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8971)
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
                                     line_num=8997)
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
        exp_caller_info = exp_caller_info._replace(line_num=9006)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9015)
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
        exp_caller_info = exp_caller_info._replace(line_num=9028)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9035)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9042)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9049)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9056)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9063)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9070)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9078)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9085)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9092)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9099)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9106)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9113)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9120)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9127)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9134)
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
                                     line_num=9161)
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
        exp_caller_info = exp_caller_info._replace(line_num=9170)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9179)
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
        exp_caller_info = exp_caller_info._replace(line_num=9192)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9199)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9206)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9213)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9220)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9227)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9234)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9242)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9249)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9256)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9263)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9270)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9277)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9284)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9291)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9298)
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
                                     line_num=9324)
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
        exp_caller_info = exp_caller_info._replace(line_num=9333)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9342)
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
        exp_caller_info = exp_caller_info._replace(line_num=9355)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9360)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9366)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9373)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9377)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9381)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9386)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9393)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9397)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9402)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9409)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9416)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9423)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9430)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9437)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9444)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9451)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9459)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9466)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9473)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9480)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9487)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9494)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9501)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9508)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9515)
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
                                     line_num=9541)
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
        exp_caller_info = exp_caller_info._replace(line_num=9550)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9559)
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
        exp_caller_info = exp_caller_info._replace(line_num=9573)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9579)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9586)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9591)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9598)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9603)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9610)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9617)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9624)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9631)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9638)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9645)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9652)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9660)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9667)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9674)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9681)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9688)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9695)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9702)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9709)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9716)
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
                                     line_num=9743)
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
        exp_caller_info = exp_caller_info._replace(line_num=9752)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9761)
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
        exp_caller_info = exp_caller_info._replace(line_num=9775)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9781)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9788)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s2bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9793)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9797)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9802)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9809)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9813)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9817)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9822)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9829)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9836)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9843)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9850)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9857)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9864)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9871)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9879)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9886)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9893)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9900)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9907)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9914)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9921)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9928)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9935)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3sb(exp_stack=exp_stack,
                                                  capsys=capsys)

        exp_stack.pop()


###############################################################################
# Class 3
###############################################################################
class ClassGetCallerInfo3:
    """Class to get caller info3."""

    def __init__(self):
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
                                     line_num=9973)
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
        exp_caller_info = exp_caller_info._replace(line_num=9982)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9991)
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
                                     line_num=10023)
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
        exp_caller_info = exp_caller_info._replace(line_num=10032)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10041)
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
                                     line_num=10073)
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
        exp_caller_info = exp_caller_info._replace(line_num=10082)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10091)
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
                                     line_num=10123)
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
        exp_caller_info = exp_caller_info._replace(line_num=10132)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10141)
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
                                     line_num=10173)
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
        exp_caller_info = exp_caller_info._replace(line_num=10182)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10191)
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
                                     line_num=10224)
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
        exp_caller_info = exp_caller_info._replace(line_num=10233)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10242)
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
                                     line_num=10275)
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
        exp_caller_info = exp_caller_info._replace(line_num=10284)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10293)
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
                                     line_num=10325)
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
        exp_caller_info = exp_caller_info._replace(line_num=10334)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10343)
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
                                     line_num=10376)
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
        exp_caller_info = exp_caller_info._replace(line_num=10385)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10394)
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

    def __init__(self):
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
                                     line_num=10438)
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
        exp_caller_info = exp_caller_info._replace(line_num=10447)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10456)
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
                                     line_num=10488)
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
        exp_caller_info = exp_caller_info._replace(line_num=10497)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10506)
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
                                     line_num=10539)
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
        exp_caller_info = exp_caller_info._replace(line_num=10548)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10557)
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
                                     line_num=10589)
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
        exp_caller_info = exp_caller_info._replace(line_num=10598)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10607)
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
                                     line_num=10639)
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
        exp_caller_info = exp_caller_info._replace(line_num=10648)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10657)
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
                                     line_num=10690)
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
        exp_caller_info = exp_caller_info._replace(line_num=10699)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10708)
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
                                     line_num=10740)
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
        exp_caller_info = exp_caller_info._replace(line_num=10749)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10758)
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
        exp_caller_info = exp_caller_info._replace(line_num=10771)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10776)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10782)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10789)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10793)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10797)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10802)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10809)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10813)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10818)
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
                                     line_num=10844)
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
        exp_caller_info = exp_caller_info._replace(line_num=10853)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10862)
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
        exp_caller_info = exp_caller_info._replace(line_num=10876)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10882)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10889)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10894)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10901)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10906)
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

        # call base class normal method target
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10965)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10971)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10978)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s3bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10983)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10987)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10992)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10999)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11003)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11007)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11012)
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
                              line_num=11035)

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
exp_caller_info0 = exp_caller_info0._replace(line_num=11046)
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
exp_caller_info0 = exp_caller_info0._replace(line_num=11065)
exp_stack0.append(exp_caller_info0)
func_get_caller_info_1(exp_stack=exp_stack0, capsys=None)

# call method
cls_get_caller_info01 = ClassGetCallerInfo1()
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11073)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_m1(exp_stack=exp_stack0, capsys=None)

# call static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11080)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_s1(exp_stack=exp_stack0, capsys=None)

# call class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11087)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack0, capsys=None)

# call overloaded base class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11094)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11101)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11108)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call subclass method
cls_get_caller_info01S = ClassGetCallerInfo1S()
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11116)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1s(exp_stack=exp_stack0, capsys=None)

# call subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11123)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1s(exp_stack=exp_stack0, capsys=None)

# call subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11130)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11137)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11144)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11151)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call base method from subclass method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11158)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1sb(exp_stack=exp_stack0, capsys=None)

# call base static method from subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11165)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1sb(exp_stack=exp_stack0, capsys=None)

# call base class method from subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11172)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack0, capsys=None)
