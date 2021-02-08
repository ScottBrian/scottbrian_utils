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
    """Verify the captured msg is as expected.

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
    def test_get_caller_info_helper(self, capsys: Any) -> None:
        """Get capsys for static methods.

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
            exp_stack: The expected call stack
            capsys: Pytest fixture that captures output

        """
        exp_caller_info = CallerInfo(mod_name='test_diag_msg.py',
                                     cls_name='TestClassGetCallerInfo0',
                                     func_name='get_caller_info_s0',
                                     line_num=856)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=865)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=2)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=874)
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
        exp_caller_info = exp_caller_info._replace(line_num=887)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=894)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=901)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=908)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=915)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=922)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=929)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=937)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=944)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=951)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=958)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=965)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=972)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=979)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=986)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=993)
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
                                     line_num=1018)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1027)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1036)
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
        exp_caller_info = exp_caller_info._replace(line_num=1049)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1056)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1063)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1070)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1077)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1084)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1091)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1099)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1106)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1113)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1120)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1127)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1134)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1141)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1148)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1155)
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
                                     line_num=1180)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1189)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1198)
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
        exp_caller_info = exp_caller_info._replace(line_num=1211)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1218)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1225)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1232)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1239)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1246)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1253)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1261)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1268)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1275)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1282)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1289)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1296)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1303)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1310)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1317)
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
                                     line_num=1342)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1351)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1360)
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
        exp_caller_info = exp_caller_info._replace(line_num=1373)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1380)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1387)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1394)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1401)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1408)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1415)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1423)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1430)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1437)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1444)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1451)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1458)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1465)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1472)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1479)
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
                                     line_num=1505)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1514)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1523)
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
        exp_caller_info = exp_caller_info._replace(line_num=1536)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1543)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1550)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1557)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1564)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1571)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1578)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1586)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1593)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1600)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1607)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1614)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1621)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1628)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1635)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1642)
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
                                     line_num=1667)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1676)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1685)
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
        exp_caller_info = exp_caller_info._replace(line_num=1698)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1705)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1712)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1719)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1726)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1733)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1740)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1748)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1755)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1762)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1769)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1776)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1783)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1790)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1797)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1804)
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
                                     line_num=1830)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1839)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1848)
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
        exp_caller_info = exp_caller_info._replace(line_num=1861)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1868)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1875)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1882)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1889)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1896)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1903)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1911)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1918)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1925)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1932)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1939)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1946)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1953)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1960)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=1967)
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
                                  capsys: Any
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
                                     line_num=1996)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2005)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2014)
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
        exp_caller_info = exp_caller_info._replace(line_num=2027)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2034)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2041)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2048)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2055)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2062)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2069)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2077)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2084)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2091)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2098)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2105)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2112)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2119)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2126)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2133)
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
                                     line_num=2164)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2173)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2182)
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
        exp_caller_info = exp_caller_info._replace(line_num=2195)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2202)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2209)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2216)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2223)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2230)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2237)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2245)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2252)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2259)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2266)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2273)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2280)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2287)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2294)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2301)
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
                                     line_num=2326)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2335)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2344)
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
        exp_caller_info = exp_caller_info._replace(line_num=2357)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2364)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2371)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2378)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2385)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2392)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2399)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2407)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2414)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2421)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2428)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2435)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2442)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2449)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2456)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2463)
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
                                     line_num=2489)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2498)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2507)
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
        exp_caller_info = exp_caller_info._replace(line_num=2520)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2527)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2534)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2541)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2548)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2555)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2562)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2570)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2577)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2584)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2591)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2598)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2605)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2612)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2619)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2626)
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
                                     line_num=2651)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2660)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2669)
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
        exp_caller_info = exp_caller_info._replace(line_num=2682)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2689)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2696)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2703)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2710)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2717)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2724)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2732)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2739)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2746)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2753)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2760)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2767)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2774)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2781)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2788)
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
                                     line_num=2813)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2822)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2831)
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
        exp_caller_info = exp_caller_info._replace(line_num=2844)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2851)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2858)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2865)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2872)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2879)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2886)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2894)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2901)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2908)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2915)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2922)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2929)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2936)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2943)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2950)
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
                                     line_num=2976)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2985)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=2994)
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
        exp_caller_info = exp_caller_info._replace(line_num=3007)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3014)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3021)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3028)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3035)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3042)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3049)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3057)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3064)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3071)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3078)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3085)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3092)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3099)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3106)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3113)
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
                                     line_num=3138)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3147)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3156)
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
        exp_caller_info = exp_caller_info._replace(line_num=3169)
        exp_stack.append(exp_caller_info)
        self.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0 = TestClassGetCallerInfo0()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3174)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3179)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3185)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3189)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3193)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3198)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3205)
        exp_stack.append(exp_caller_info)
        super().test_get_caller_info_c0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3209)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3214)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3221)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3228)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3235)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3242)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3249)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3256)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3263)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3271)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3278)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3285)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3292)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3299)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3306)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3313)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3320)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3327)
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
                                     line_num=3352)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3361)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3370)
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
        exp_caller_info = exp_caller_info._replace(line_num=3384)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3389)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3395)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3400)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3407)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                          capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3412)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.test_get_caller_info_c0bt(exp_stack=exp_stack,
                                                           capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3419)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3426)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3433)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3440)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3447)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3454)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3461)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3469)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3476)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3483)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3490)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3497)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3504)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3511)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3518)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3525)
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
                                     line_num=3551)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3560)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=1)

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        # test diag_msg
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3569)
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
        exp_caller_info = exp_caller_info._replace(line_num=3583)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0.test_get_caller_info_m0bt(capsys=capsys)
        tst_cls_get_caller_info0s = TestClassGetCallerInfo0S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3588)
        exp_stack.append(exp_caller_info)
        tst_cls_get_caller_info0s.test_get_caller_info_m0bt(capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3594)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s0bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3599)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s0bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3603)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0.get_caller_info_s0bt(exp_stack=exp_stack,
                                                     capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3608)
        exp_stack.append(exp_caller_info)
        TestClassGetCallerInfo0S.get_caller_info_s0bt(exp_stack=exp_stack,
                                                      capsys=capsys)
        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3614)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_1(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3621)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3628)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3635)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3642)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3649)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_s1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3656)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3664)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3671)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3678)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3685)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3692)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3699)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3706)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3713)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_s1sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3720)
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
                                     line_num=3758)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3767)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=3776)
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
        exp_caller_info = exp_caller_info._replace(line_num=3789)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3796)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3803)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3810)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3817)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3824)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3831)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3839)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3846)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3853)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3860)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3867)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3874)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3881)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3888)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3895)
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
                                     line_num=3921)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3930)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=3939)
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
        exp_caller_info = exp_caller_info._replace(line_num=3952)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3959)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3966)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3973)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3980)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3987)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=3994)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4002)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4009)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4016)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4023)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4030)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4037)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4044)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4051)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4058)
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
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4102)
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
        exp_caller_info = exp_caller_info._replace(line_num=4115)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4122)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4129)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4136)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4143)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4150)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4157)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4165)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4172)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4179)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4186)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4193)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4200)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4207)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4214)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4221)
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
                                     line_num=4247)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4256)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4265)
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
        exp_caller_info = exp_caller_info._replace(line_num=4278)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4285)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4292)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4299)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4306)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4313)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4320)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4328)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4335)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4342)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4349)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4356)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4363)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4370)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4377)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4384)
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
                                     line_num=4410)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4419)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4428)
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
        exp_caller_info = exp_caller_info._replace(line_num=4441)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4448)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4455)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4462)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4469)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4476)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4483)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4491)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4498)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4505)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4512)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4519)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4526)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4533)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4540)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4547)
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
                                     line_num=4574)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4583)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4592)
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
        exp_caller_info = exp_caller_info._replace(line_num=4605)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4612)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4619)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4626)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4633)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4640)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4647)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4655)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4662)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4669)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4676)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4683)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4690)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4697)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4704)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4711)
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
                                     line_num=4738)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4747)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4756)
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
        exp_caller_info = exp_caller_info._replace(line_num=4769)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4776)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4783)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4790)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4797)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4804)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4811)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4819)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4826)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4833)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4840)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4847)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4854)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4861)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4868)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4875)
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
                                     line_num=4901)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4910)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=4919)
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
        exp_caller_info = exp_caller_info._replace(line_num=4932)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4939)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4946)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4953)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4960)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4967)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4974)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4982)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4989)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=4996)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5003)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5010)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5017)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5024)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5031)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5038)
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
                                     line_num=5065)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5074)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5083)
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
        exp_caller_info = exp_caller_info._replace(line_num=5096)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5103)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5110)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5117)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5124)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5131)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5138)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5146)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5153)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5160)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5167)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5174)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5181)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5188)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5195)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5202)
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
                                     line_num=5240)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5249)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5258)
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
        exp_caller_info = exp_caller_info._replace(line_num=5271)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5278)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5285)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5292)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5299)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5306)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5313)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5321)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5328)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5335)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5342)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5349)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5356)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5363)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5370)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5377)
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
                                     line_num=5403)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5412)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5421)
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
        exp_caller_info = exp_caller_info._replace(line_num=5434)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5441)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5448)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5455)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5462)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5469)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5476)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5484)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5491)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5498)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5505)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5512)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5519)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5526)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5533)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5540)
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
                                     line_num=5567)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5576)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5585)
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
        exp_caller_info = exp_caller_info._replace(line_num=5598)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5605)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5612)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5619)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5626)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5633)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5640)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5648)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5655)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5662)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5669)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5676)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5683)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5690)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5697)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5704)
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
                                     line_num=5730)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5739)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5748)
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
        exp_caller_info = exp_caller_info._replace(line_num=5761)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5768)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5775)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5782)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5789)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5796)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5803)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5811)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5818)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5825)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5832)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5839)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5846)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5853)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5860)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5867)
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
                                     line_num=5893)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5902)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=5911)
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
        exp_caller_info = exp_caller_info._replace(line_num=5924)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5931)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5938)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5945)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5952)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5959)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5966)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5974)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5981)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5988)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=5995)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6002)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6009)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6016)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6023)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6030)
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
                                     line_num=6057)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6066)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6075)
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
        exp_caller_info = exp_caller_info._replace(line_num=6088)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6095)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6102)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6109)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6116)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6123)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6130)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6138)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6145)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6152)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6159)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6166)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6173)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6180)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6187)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6194)
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
                                     line_num=6220)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6229)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6238)
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
        exp_caller_info = exp_caller_info._replace(line_num=6251)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m1bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info1 = ClassGetCallerInfo1()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6256)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6262)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6269)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6273)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6277)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6282)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6289)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6293)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6298)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6305)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6312)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6319)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6326)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6333)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6340)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6347)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6355)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6362)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6369)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6376)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6383)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6390)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6397)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6404)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6411)
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
                                     line_num=6437)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6446)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6455)
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
        exp_caller_info = exp_caller_info._replace(line_num=6469)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6475)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6482)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6487)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6494)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6499)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6506)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6513)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6520)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6527)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6534)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6541)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6548)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6556)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6563)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6570)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6577)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6584)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6591)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6598)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6605)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6612)
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
                                     line_num=6639)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6648)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6657)
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
        exp_caller_info = exp_caller_info._replace(line_num=6671)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1.get_caller_info_m1bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info1s = ClassGetCallerInfo1S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6677)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info1s.get_caller_info_m1bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6684)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s1bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6689)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6693)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_s1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6698)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_s1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6705)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6709)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c1bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6713)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1.get_caller_info_c1bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6718)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo1S.get_caller_info_c1bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6725)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6732)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6739)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6746)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6753)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6760)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_s2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6767)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6775)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6782)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6789)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6796)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6803)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6810)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6817)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6824)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_s2sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6831)
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
                                     line_num=6869)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6878)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=6887)
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
        exp_caller_info = exp_caller_info._replace(line_num=6900)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6907)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6914)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6921)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6928)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6935)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6942)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6950)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6957)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6964)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6971)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6978)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6985)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6992)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=6999)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7006)
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
                                     line_num=7032)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7041)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7050)
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
        exp_caller_info = exp_caller_info._replace(line_num=7063)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7070)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7077)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7084)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7091)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7098)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7105)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7113)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7120)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7127)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7134)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7141)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7148)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7155)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7162)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7169)
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
                                     line_num=7195)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7204)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7213)
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
        exp_caller_info = exp_caller_info._replace(line_num=7226)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7233)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7240)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7247)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7254)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7261)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7268)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7276)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7283)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7290)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7297)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7304)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7311)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7318)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7325)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7332)
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
                                     line_num=7358)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7367)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7376)
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
        exp_caller_info = exp_caller_info._replace(line_num=7389)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7396)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7403)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7410)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7417)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7424)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7431)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7439)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7446)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7453)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7460)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7467)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7474)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7481)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7488)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7495)
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
                                     line_num=7521)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7530)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7539)
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
        exp_caller_info = exp_caller_info._replace(line_num=7552)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7559)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7566)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7573)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7580)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7587)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7594)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7602)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7609)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7616)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7623)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7630)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7637)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7644)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7651)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7658)
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
                                     line_num=7685)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7694)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7703)
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
        exp_caller_info = exp_caller_info._replace(line_num=7716)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7723)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7730)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7737)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7744)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7751)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7758)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7766)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7773)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7780)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7787)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7794)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7801)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7808)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7815)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7822)
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
                                     line_num=7849)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7858)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=7867)
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
        exp_caller_info = exp_caller_info._replace(line_num=7880)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7887)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7894)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7901)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7908)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7915)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7922)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7930)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7937)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7944)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7951)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7958)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7965)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7972)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7979)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=7986)
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
                                     line_num=8012)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8021)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8030)
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
        exp_caller_info = exp_caller_info._replace(line_num=8043)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8050)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8057)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8064)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8071)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8078)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8085)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8093)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8100)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8107)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8114)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8121)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8128)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8135)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8142)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8149)
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
                                     line_num=8176)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8185)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8194)
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
        exp_caller_info = exp_caller_info._replace(line_num=8207)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8214)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8221)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8228)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8235)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8242)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8249)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8257)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8264)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8271)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8278)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8285)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8292)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8299)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8306)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8313)
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
                                     line_num=8351)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8360)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8369)
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
        exp_caller_info = exp_caller_info._replace(line_num=8382)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8389)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8396)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8403)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8410)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8417)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8424)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8432)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8439)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8446)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8453)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8460)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8467)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8474)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8481)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8488)
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
                                     line_num=8514)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8523)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8532)
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
        exp_caller_info = exp_caller_info._replace(line_num=8545)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8552)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8559)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8566)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8573)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8580)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8587)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8595)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8602)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8609)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8616)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8623)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8630)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8637)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8644)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8651)
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
                                     line_num=8678)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8687)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8696)
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
        exp_caller_info = exp_caller_info._replace(line_num=8709)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8716)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8723)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8730)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8737)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8744)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8751)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8759)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8766)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8773)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8780)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8787)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8794)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8801)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8808)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8815)
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
                                     line_num=8841)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8850)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=8859)
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
        exp_caller_info = exp_caller_info._replace(line_num=8872)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8879)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8886)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8893)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8900)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8907)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8914)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8922)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8929)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8936)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8943)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8950)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8957)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8964)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8971)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=8978)
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
                                     line_num=9004)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9013)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9022)
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
        exp_caller_info = exp_caller_info._replace(line_num=9035)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9042)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9049)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9056)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9063)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9070)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9077)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9085)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9092)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9099)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9106)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9113)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9120)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9127)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9134)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9141)
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
                                     line_num=9168)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9177)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9186)
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
        exp_caller_info = exp_caller_info._replace(line_num=9199)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9206)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9213)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9220)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9227)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9234)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9241)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9249)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9256)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9263)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9270)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9277)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9284)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9291)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9298)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9305)
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
                                     line_num=9331)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9340)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9349)
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
        exp_caller_info = exp_caller_info._replace(line_num=9362)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m2bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info2 = ClassGetCallerInfo2()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9367)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9373)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9380)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9384)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9388)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9393)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9400)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9404)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9409)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9416)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_2(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9423)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9430)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9437)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9444)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9451)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9458)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9466)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9473)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9480)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9487)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9494)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9501)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9508)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9515)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9522)
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
                                     line_num=9548)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9557)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9566)
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
        exp_caller_info = exp_caller_info._replace(line_num=9580)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9586)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9593)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9598)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9605)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9610)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9617)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9624)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9631)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9638)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9645)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9652)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9659)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9667)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9674)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9681)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9688)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9695)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9702)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9709)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9716)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9723)
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
                                     line_num=9750)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9759)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9768)
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
        exp_caller_info = exp_caller_info._replace(line_num=9782)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2.get_caller_info_m2bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info2s = ClassGetCallerInfo2S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9788)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info2s.get_caller_info_m2bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9795)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s2bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9800)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9804)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_s2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9809)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_s2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9816)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9820)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c2bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9824)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2.get_caller_info_c2bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9829)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo2S.get_caller_info_c2bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call module level function
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9836)
        exp_stack.append(exp_caller_info)
        func_get_caller_info_3(exp_stack=exp_stack, capsys=capsys)

        # call method
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9843)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9850)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3(exp_stack=exp_stack,
                                                capsys=capsys)

        # call class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9857)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3(exp_stack=exp_stack,
                                               capsys=capsys)

        # call overloaded base class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9864)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9871)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_s3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call overloaded base class class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9878)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bo(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call subclass method
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9886)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9893)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3s(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9900)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3s(exp_stack=exp_stack,
                                                 capsys=capsys)

        # call overloaded subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9907)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9914)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3bo(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call overloaded subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9921)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_c3bo(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base method from subclass method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9928)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base static method from subclass static method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9935)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_s3sb(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class method from subclass class method
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9942)
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
                                     line_num=9980)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=9989)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=9998)
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
                                     line_num=10030)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10039)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10048)
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
                                     line_num=10080)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10089)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10098)
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
                                     line_num=10130)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10139)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10148)
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
                                     line_num=10180)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10189)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10198)
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
                                     line_num=10231)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10240)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10249)
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
                                     line_num=10282)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10291)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10300)
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
                                     line_num=10332)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10341)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10350)
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
                                     line_num=10383)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10392)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10401)
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
                                     line_num=10445)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10454)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10463)
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
                                     line_num=10495)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10504)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10513)
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
                                     line_num=10546)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10555)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10564)
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
                                     line_num=10596)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10605)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10614)
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
                                     line_num=10646)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10655)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10664)
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
                                     line_num=10697)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10706)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10715)
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
                                     line_num=10747)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10756)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10765)
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
        exp_caller_info = exp_caller_info._replace(line_num=10778)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_m3bt(exp_stack=exp_stack, capsys=capsys)
        cls_get_caller_info3 = ClassGetCallerInfo3()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10783)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10789)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10796)
        exp_stack.append(exp_caller_info)
        self.get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10800)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10804)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10809)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10816)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10820)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10825)
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
                                     line_num=10851)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10860)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10869)
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
        exp_caller_info = exp_caller_info._replace(line_num=10883)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10889)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10896)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10901)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10908)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10913)
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
                                     line_num=10940)
        exp_stack.append(exp_caller_info)
        for i, expected_caller_info in enumerate(list(reversed(exp_stack))):
            try:
                frame = _getframe(i)
                caller_info = get_caller_info(frame)
            finally:
                del frame
            assert caller_info == expected_caller_info

        # test call sequence
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10949)
        exp_stack.append(exp_caller_info)
        call_seq = get_formatted_call_sequence(depth=len(exp_stack))

        assert call_seq == get_exp_seq(exp_stack=exp_stack)

        if capsys:  # if capsys, test diag_msg
            exp_stack.pop()
            exp_caller_info = exp_caller_info._replace(line_num=10958)
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
        exp_caller_info = exp_caller_info._replace(line_num=10972)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3.get_caller_info_m3bt(exp_stack=exp_stack,
                                                  capsys=capsys)
        cls_get_caller_info3s = ClassGetCallerInfo3S()
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10978)
        exp_stack.append(exp_caller_info)
        cls_get_caller_info3s.get_caller_info_m3bt(exp_stack=exp_stack,
                                                   capsys=capsys)

        # call base class static method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10985)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_s3bt(exp_stack=exp_stack,
                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10990)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_s3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10994)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_s3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=10999)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3S.get_caller_info_s3bt(exp_stack=exp_stack,
                                                  capsys=capsys)

        # call base class class method target
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11006)
        exp_stack.append(exp_caller_info)
        cls.get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11010)
        exp_stack.append(exp_caller_info)
        super().get_caller_info_c3bt(exp_stack=exp_stack, capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11014)
        exp_stack.append(exp_caller_info)
        ClassGetCallerInfo3.get_caller_info_c3bt(exp_stack=exp_stack,
                                                 capsys=capsys)
        exp_stack.pop()
        exp_caller_info = exp_caller_info._replace(line_num=11019)
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
                              line_num=11042)

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
exp_caller_info0 = exp_caller_info0._replace(line_num=11053)
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
exp_caller_info0 = exp_caller_info0._replace(line_num=11072)
exp_stack0.append(exp_caller_info0)
func_get_caller_info_1(exp_stack=exp_stack0, capsys=None)

# call method
cls_get_caller_info01 = ClassGetCallerInfo1()
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11080)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_m1(exp_stack=exp_stack0, capsys=None)

# call static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11087)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_s1(exp_stack=exp_stack0, capsys=None)

# call class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11094)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1.get_caller_info_c1(exp_stack=exp_stack0, capsys=None)

# call overloaded base class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11101)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11108)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded base class class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11115)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call subclass method
cls_get_caller_info01S = ClassGetCallerInfo1S()
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11123)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1s(exp_stack=exp_stack0, capsys=None)

# call subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11130)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1s(exp_stack=exp_stack0, capsys=None)

# call subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11137)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1s(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11144)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11151)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1bo(exp_stack=exp_stack0, capsys=None)

# call overloaded subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11158)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1bo(exp_stack=exp_stack0, capsys=None)

# call base method from subclass method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11165)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_m1sb(exp_stack=exp_stack0, capsys=None)

# call base static method from subclass static method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11172)
exp_stack0.append(exp_caller_info0)
cls_get_caller_info01S.get_caller_info_s1sb(exp_stack=exp_stack0, capsys=None)

# call base class method from subclass class method
exp_stack0.pop()
# noinspection PyProtectedMember
exp_caller_info0 = exp_caller_info0._replace(line_num=11179)
exp_stack0.append(exp_caller_info0)
ClassGetCallerInfo1S.get_caller_info_c1sb(exp_stack=exp_stack0, capsys=None)
