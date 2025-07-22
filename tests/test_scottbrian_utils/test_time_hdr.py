"""test_timer.py module."""

########################################################################
# Standard Library
########################################################################
import inspect
import logging
import sys
import threading
import time
from typing import Any, cast, Optional, Union

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.timer import Timer
from scottbrian_utils.stop_watch import StopWatch

logger = logging.getLogger(__name__)

########################################################################
# type aliases
########################################################################
IntFloat = Union[int, float]
OptIntFloat = Optional[IntFloat]


########################################################################
# Timer test exceptions
########################################################################
class ErrorTstTimer(Exception):
    """Base class for exception in this module."""

    pass


########################################################################
# timeout arg fixtures
# greater_than_zero_timeout_arg fixture
########################################################################
zero_or_less_timeout_arg_list = [-1.1, -1, 0, 0.0]
greater_than_zero_timeout_arg_list = [0.3, 0.5, 1, 1.5, 2, 4]


########################################################################
# timeout_arg fixture
########################################################################
@pytest.fixture(params=greater_than_zero_timeout_arg_list)
def timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


########################################################################
# zero_or_less_timeout_arg fixture
########################################################################
@pytest.fixture(params=zero_or_less_timeout_arg_list)
def zero_or_less_timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


########################################################################
# greater_than_zero_timeout_arg fixture
########################################################################
@pytest.fixture(params=greater_than_zero_timeout_arg_list)
def greater_than_zero_timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


########################################################################
# zero_or_less_default_timeout_arg fixture
########################################################################
@pytest.fixture(params=zero_or_less_timeout_arg_list)
def zero_or_less_default_timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout_default.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


########################################################################
# greater_than_zero_default_timeout_arg fixture
########################################################################
@pytest.fixture(params=greater_than_zero_timeout_arg_list)
def greater_than_zero_default_timeout_arg(request: Any) -> IntFloat:
    """Using different seconds for timeout_default.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(IntFloat, request.param)


########################################################################
# TestTimerExamples class
########################################################################
class TestTimerExamples:
    """Test examples of Timer."""

    ####################################################################
    # test_timer_example1
    ####################################################################
    def test_timer_example1(self, capsys: Any) -> None:
        """Test timer example1.

        Args:
            capsys: pytest fixture to capture print output

        """
        print("mainline entered")
        timer = Timer(timeout=3)
        for idx in range(10):
            print(f"idx = {idx}")
            time.sleep(1)
            if timer.is_expired():
                print("timer has expired")
                break
        print("mainline exiting")

        expected_result = "mainline entered\n"
        expected_result += "idx = 0\n"
        expected_result += "idx = 1\n"
        expected_result += "idx = 2\n"
        expected_result += "timer has expired\n"
        expected_result += "mainline exiting\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_timer_example2
    ####################################################################
    def test_timer_example2(self, capsys: Any) -> None:
        """Test timer example2.

        Args:
            capsys: pytest fixture to capture print output

        """

        class A:
            def __init__(self) -> None:
                self.a = 1

            def m1(self, sleep_time: float) -> bool:
                timer = Timer(timeout=1)
                time.sleep(sleep_time)
                if timer.is_expired():
                    return False
                return True

        print("mainline entered")
        my_a = A()
        print(my_a.m1(0.5))
        print(my_a.m1(1.5))
        print("mainline exiting")

        expected_result = "mainline entered\n"
        expected_result += "True\n"
        expected_result += "False\n"
        expected_result += "mainline exiting\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_timer_example3
    ####################################################################
    def test_timer_example3(self, capsys: Any) -> None:
        """Test timer example3.

        Args:
            capsys: pytest fixture to capture print output

        """

        class A:
            def __init__(self) -> None:
                self.a = 1

            def m1(self, sleep_time: float, timeout: float) -> bool:
                timer = Timer(timeout=timeout)
                time.sleep(sleep_time)
                if timer.is_expired():
                    return False
                return True

        print("mainline entered")
        my_a = A()
        print(my_a.m1(sleep_time=0.5, timeout=0.7))
        print(my_a.m1(sleep_time=1.5, timeout=1.2))
        print(my_a.m1(sleep_time=1.5, timeout=1.8))
        print("mainline exiting")

        expected_result = "mainline entered\n"
        expected_result += "True\n"
        expected_result += "False\n"
        expected_result += "True\n"
        expected_result += "mainline exiting\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_timer_example4
    ####################################################################
    def test_timer_example4(self, capsys: Any) -> None:
        """Test timer example4.

        Args:
            capsys: pytest fixture to capture print output

        """

        class A:
            def __init__(self, default_timeout: float):
                self.a = 1
                self.default_timeout = default_timeout

            def m1(self, sleep_time: float, timeout: Optional[float] = None) -> bool:
                timer = Timer(timeout=timeout, default_timeout=self.default_timeout)
                time.sleep(sleep_time)
                if timer.is_expired():
                    return False
                return True

        print("mainline entered")
        my_a = A(default_timeout=1.2)
        print(my_a.m1(sleep_time=0.5))
        print(my_a.m1(sleep_time=1.5))
        print(my_a.m1(sleep_time=0.5, timeout=0.3))
        print(my_a.m1(sleep_time=1.5, timeout=1.8))
        print(my_a.m1(sleep_time=1.5, timeout=0))
        print("mainline exiting")

        expected_result = "mainline entered\n"
        expected_result += "True\n"
        expected_result += "False\n"
        expected_result += "False\n"
        expected_result += "True\n"
        expected_result += "True\n"
        expected_result += "mainline exiting\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_timer_example5
    ####################################################################
    def test_timer_example5(self, capsys: Any) -> None:
        """Test timer example5.

        Args:
            capsys: pytest fixture to capture print output

        """

        def f1() -> None:
            print("f1 entered")
            time.sleep(1)
            f1_event.set()
            time.sleep(1)
            f1_event.set()
            time.sleep(1)
            f1_event.set()
            print("f1 exiting")

        print("mainline entered")
        timer = Timer(timeout=2.5)
        f1_thread = threading.Thread(target=f1)
        f1_event = threading.Event()
        f1_thread.start()
        wait_result = f1_event.wait(timeout=timer.remaining_time())
        print(f"wait1 result = {wait_result}")
        f1_event.clear()
        print(f"remaining time = {timer.remaining_time():0.1f}")
        print(f"timer expired = {timer.is_expired()}")
        wait_result = f1_event.wait(timeout=timer.remaining_time())
        print(f"wait2 result = {wait_result}")
        f1_event.clear()
        print(f"remaining time = {timer.remaining_time():0.1f}")
        print(f"timer expired = {timer.is_expired()}")
        wait_result = f1_event.wait(timeout=timer.remaining_time())
        print(f"wait3 result = {wait_result}")
        f1_event.clear()
        print(f"remaining time = {timer.remaining_time():0.4f}")
        print(f"timer expired = {timer.is_expired()}")
        f1_thread.join()
        print("mainline exiting")

        expected_result = "mainline entered\n"
        expected_result += "f1 entered\n"
        expected_result += "wait1 result = True\n"
        expected_result += "remaining time = 1.5\n"
        expected_result += "timer expired = False\n"
        expected_result += "wait2 result = True\n"
        expected_result += "remaining time = 0.5\n"
        expected_result += "timer expired = False\n"
        expected_result += "wait3 result = False\n"
        expected_result += "remaining time = 0.0001\n"
        expected_result += "timer expired = True\n"
        expected_result += "f1 exiting\n"
        expected_result += "mainline exiting\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_timer_example6
    ####################################################################
    def test_timer_example6(self, capsys: Any) -> None:
        """Test timer example6.

        Args:
            capsys: pytest fixture to capture print output

        """
        print("mainline entered")
        timer = Timer(timeout=2.5)
        time.sleep(1)
        print(f"timer expired = {timer.is_expired()}")
        time.sleep(1)
        print(f"timer expired = {timer.is_expired()}")
        time.sleep(1)
        print(f"timer expired = {timer.is_expired()}")
        print("mainline exiting")

        expected_result = "mainline entered\n"
        expected_result += "timer expired = False\n"
        expected_result += "timer expired = False\n"
        expected_result += "timer expired = True\n"
        expected_result += "mainline exiting\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_timer_example6
    ####################################################################
    def test_timer_example7(self, capsys: Any) -> None:
        """Test timer example7.

        Args:
            capsys: pytest fixture to capture print output

        """
        print("example7 entered")
        timer_a = Timer()
        print(f"timer_a specified = {timer_a.is_specified()}")
        timer_b = Timer(timeout=None)
        print(f"timer_b specified = {timer_b.is_specified()}")
        timer_c = Timer(timeout=-1)
        print(f"timer_c specified = {timer_c.is_specified()}")
        timer_d = Timer(timeout=0)
        print(f"timer_d specified = {timer_d.is_specified()}")
        timer_e = Timer(timeout=1)
        print(f"timer_e specified = {timer_e.is_specified()}")
        timer_f = Timer(default_timeout=None)
        print(f"timer_f specified = {timer_f.is_specified()}")
        timer_g = Timer(default_timeout=-1)
        print(f"timer_g specified = {timer_g.is_specified()}")
        timer_h = Timer(default_timeout=0)
        print(f"timer_h specified = {timer_h.is_specified()}")
        timer_i = Timer(default_timeout=1)
        print(f"timer_i specified = {timer_i.is_specified()}")
        timer_j = Timer(timeout=None, default_timeout=None)
        print(f"timer_j specified = {timer_j.is_specified()}")
        timer_k = Timer(timeout=None, default_timeout=-1)
        print(f"timer_k specified = {timer_k.is_specified()}")
        timer_l = Timer(timeout=None, default_timeout=0)
        print(f"timer_l specified = {timer_l.is_specified()}")
        timer_m = Timer(timeout=None, default_timeout=1)
        print(f"timer_m specified = {timer_m.is_specified()}")
        timer_n = Timer(timeout=-1, default_timeout=None)
        print(f"timer_n specified = {timer_n.is_specified()}")
        timer_o = Timer(timeout=-1, default_timeout=-1)
        print(f"timer_o specified = {timer_o.is_specified()}")
        timer_p = Timer(timeout=-1, default_timeout=0)
        print(f"timer_p specified = {timer_p.is_specified()}")
        timer_q = Timer(timeout=-1, default_timeout=1)
        print(f"timer_q specified = {timer_q.is_specified()}")
        timer_r = Timer(timeout=0, default_timeout=None)
        print(f"timer_r specified = {timer_r.is_specified()}")
        timer_s = Timer(timeout=0, default_timeout=-1)
        print(f"timer_s specified = {timer_s.is_specified()}")
        timer_t = Timer(timeout=0, default_timeout=0)
        print(f"timer_t specified = {timer_t.is_specified()}")
        timer_u = Timer(timeout=0, default_timeout=1)
        print(f"timer_u specified = {timer_u.is_specified()}")
        timer_v = Timer(timeout=1, default_timeout=None)
        print(f"timer_v specified = {timer_v.is_specified()}")
        timer_w = Timer(timeout=1, default_timeout=-1)
        print(f"timer_w specified = {timer_w.is_specified()}")
        timer_x = Timer(timeout=1, default_timeout=0)
        print(f"timer_x specified = {timer_x.is_specified()}")
        timer_y = Timer(timeout=1, default_timeout=1)
        print(f"timer_y specified = {timer_y.is_specified()}")
        print("example7 exiting")

        expected_result = "example7 entered\n"
        expected_result += "timer_a specified = False\n"
        expected_result += "timer_b specified = False\n"
        expected_result += "timer_c specified = False\n"
        expected_result += "timer_d specified = False\n"
        expected_result += "timer_e specified = True\n"
        expected_result += "timer_f specified = False\n"
        expected_result += "timer_g specified = False\n"
        expected_result += "timer_h specified = False\n"
        expected_result += "timer_i specified = True\n"
        expected_result += "timer_j specified = False\n"
        expected_result += "timer_k specified = False\n"
        expected_result += "timer_l specified = False\n"
        expected_result += "timer_m specified = True\n"
        expected_result += "timer_n specified = False\n"
        expected_result += "timer_o specified = False\n"
        expected_result += "timer_p specified = False\n"
        expected_result += "timer_q specified = False\n"
        expected_result += "timer_r specified = False\n"
        expected_result += "timer_s specified = False\n"
        expected_result += "timer_t specified = False\n"
        expected_result += "timer_u specified = False\n"
        expected_result += "timer_v specified = True\n"
        expected_result += "timer_w specified = True\n"
        expected_result += "timer_x specified = True\n"
        expected_result += "timer_y specified = True\n"
        expected_result += "example7 exiting\n"

        captured = capsys.readouterr().out

        assert captured == expected_result

    ####################################################################
    # test_timer_example6
    ####################################################################
    def test_timer_example8(self, capsys: Any) -> None:
        """Test timer example8.

        Args:
            capsys: pytest fixture to capture print output

        """
        print("example8 entered")
        timer_a = Timer()
        print(f"timer_a timeout = {timer_a.timeout_value()}")
        timer_b = Timer(timeout=None)
        print(f"timer_b timeout = {timer_b.timeout_value()}")
        timer_c = Timer(timeout=-1)
        print(f"timer_c timeout = {timer_c.timeout_value()}")
        timer_d = Timer(timeout=0)
        print(f"timer_d timeout = {timer_d.timeout_value()}")
        timer_e = Timer(timeout=1)
        print(f"timer_e timeout = {timer_e.timeout_value()}")
        timer_f = Timer(default_timeout=None)
        print(f"timer_f timeout = {timer_f.timeout_value()}")
        timer_g = Timer(default_timeout=-1)
        print(f"timer_g timeout = {timer_g.timeout_value()}")
        timer_h = Timer(default_timeout=0)
        print(f"timer_h timeout = {timer_h.timeout_value()}")
        timer_i = Timer(default_timeout=2.2)
        print(f"timer_i timeout = {timer_i.timeout_value()}")
        timer_j = Timer(timeout=None, default_timeout=None)
        print(f"timer_j timeout = {timer_j.timeout_value()}")
        timer_k = Timer(timeout=None, default_timeout=-1)
        print(f"timer_k timeout = {timer_k.timeout_value()}")
        timer_l = Timer(timeout=None, default_timeout=0)
        print(f"timer_l timeout = {timer_l.timeout_value()}")
        timer_m = Timer(timeout=None, default_timeout=2.2)
        print(f"timer_m timeout = {timer_m.timeout_value()}")
        timer_n = Timer(timeout=-1, default_timeout=None)
        print(f"timer_n timeout = {timer_n.timeout_value()}")
        timer_o = Timer(timeout=-1, default_timeout=-1)
        print(f"timer_o timeout = {timer_o.timeout_value()}")
        timer_p = Timer(timeout=-1, default_timeout=0)
        print(f"timer_p timeout = {timer_p.timeout_value()}")
        timer_q = Timer(timeout=-1, default_timeout=2.2)
        print(f"timer_q timeout = {timer_q.timeout_value()}")
        timer_r = Timer(timeout=0, default_timeout=None)
        print(f"timer_r timeout = {timer_r.timeout_value()}")
        timer_s = Timer(timeout=0, default_timeout=-1)
        print(f"timer_s timeout = {timer_s.timeout_value()}")
        timer_t = Timer(timeout=0, default_timeout=0)
        print(f"timer_t timeout = {timer_t.timeout_value()}")
        timer_u = Timer(timeout=0, default_timeout=2.2)
        print(f"timer_u timeout = {timer_u.timeout_value()}")
        timer_v = Timer(timeout=1, default_timeout=None)
        print(f"timer_v timeout = {timer_v.timeout_value()}")
        timer_w = Timer(timeout=1, default_timeout=-1)
        print(f"timer_w timeout = {timer_w.timeout_value()}")
        timer_x = Timer(timeout=1, default_timeout=0)
        print(f"timer_x timeout = {timer_x.timeout_value()}")
        timer_y = Timer(timeout=1, default_timeout=2.2)
        print(f"timer_y timeout = {timer_y.timeout_value()}")
        print("example8 exiting")

        expected_result = "example8 entered\n"
        expected_result += "timer_a timeout = None\n"
        expected_result += "timer_b timeout = None\n"
        expected_result += "timer_c timeout = None\n"
        expected_result += "timer_d timeout = None\n"
        expected_result += "timer_e timeout = 1\n"
        expected_result += "timer_f timeout = None\n"
        expected_result += "timer_g timeout = None\n"
        expected_result += "timer_h timeout = None\n"
        expected_result += "timer_i timeout = 2.2\n"
        expected_result += "timer_j timeout = None\n"
        expected_result += "timer_k timeout = None\n"
        expected_result += "timer_l timeout = None\n"
        expected_result += "timer_m timeout = 2.2\n"
        expected_result += "timer_n timeout = None\n"
        expected_result += "timer_o timeout = None\n"
        expected_result += "timer_p timeout = None\n"
        expected_result += "timer_q timeout = None\n"
        expected_result += "timer_r timeout = None\n"
        expected_result += "timer_s timeout = None\n"
        expected_result += "timer_t timeout = None\n"
        expected_result += "timer_u timeout = None\n"
        expected_result += "timer_v timeout = 1\n"
        expected_result += "timer_w timeout = 1\n"
        expected_result += "timer_x timeout = 1\n"
        expected_result += "timer_y timeout = 1\n"
        expected_result += "example8 exiting\n"

        captured = capsys.readouterr().out

        assert captured == expected_result


########################################################################
# TestTimerBasic class
########################################################################
class TestTimerBasic:
    """Test basic functions of Timer."""

    ####################################################################
    # test_timer_correct_source
    ####################################################################
    def test_timer_correct_source(self) -> None:
        """Test timer correct source."""

        # set the following four lines
        library = "C:\\Users\\Tiger\\PycharmProjects\\"
        project = "scottbrian_utils"
        py_file = "timer.py"
        class_to_use = Timer

        file_prefix = (
            f"{library}{project}\\.tox"
            f"\\py{sys.version_info.major}{sys.version_info.minor}-"
        )
        file_suffix = f"\\Lib\\site-packages\\{project}\\{py_file}"

        pytest_run = f"{file_prefix}pytest{file_suffix}"
        coverage_run = f"{file_prefix}coverage{file_suffix}"

        actual = inspect.getsourcefile(class_to_use)
        assert (actual == pytest_run) or (actual == coverage_run)

    ####################################################################
    # test_timer_case1a
    ####################################################################
    def test_timer_case1a(self) -> None:
        """Test timer case1a."""
        print("mainline entered")
        timer = Timer()
        time.sleep(1)
        assert not timer.is_expired()
        time.sleep(1)
        assert not timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case1b
    ####################################################################
    def test_timer_case1b(self) -> None:
        """Test timer case1b."""
        print("mainline entered")
        timer = Timer(default_timeout=None)
        time.sleep(1)
        assert not timer.is_expired()
        time.sleep(1)
        assert not timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case1c
    ####################################################################
    def test_timer_case1c(self) -> None:
        """Test timer case1c."""
        print("mainline entered")
        timer = Timer(timeout=None)
        time.sleep(1)
        assert not timer.is_expired()
        time.sleep(1)
        assert not timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case1d
    ####################################################################
    def test_timer_case1d(self) -> None:
        """Test timer case1d."""
        print("mainline entered")
        timer = Timer(timeout=None, default_timeout=None)
        time.sleep(1)
        assert not timer.is_expired()
        time.sleep(1)
        assert not timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case2a
    ####################################################################
    def test_timer_case2a(self, zero_or_less_default_timeout_arg: IntFloat) -> None:
        """Test timer case2a.

        Args:
            zero_or_less_default_timeout_arg: pytest fixture for timeout
                                                seconds

        """
        print("mainline entered")
        timer = Timer(default_timeout=zero_or_less_default_timeout_arg)
        time.sleep(abs(zero_or_less_default_timeout_arg * 0.9))
        assert not timer.is_expired()
        time.sleep(abs(zero_or_less_default_timeout_arg))
        assert not timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case2b
    ####################################################################

    def test_timer_case2b(self, zero_or_less_default_timeout_arg: IntFloat) -> None:
        """Test timer case2b.

        Args:
            zero_or_less_default_timeout_arg: pytest fixture for timeout
                                                seconds

        """
        print("mainline entered")
        timer = Timer(timeout=None, default_timeout=zero_or_less_default_timeout_arg)
        time.sleep(abs(zero_or_less_default_timeout_arg * 0.9))
        assert not timer.is_expired()
        time.sleep(abs(zero_or_less_default_timeout_arg))
        assert not timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case3a
    ####################################################################
    def test_timer_case3a(
        self, greater_than_zero_default_timeout_arg: IntFloat
    ) -> None:
        """Test timer case3a.

        Args:
            greater_than_zero_default_timeout_arg: pytest fixture for
                                                     timeout seconds

        """
        print("mainline entered")
        timer = Timer(default_timeout=greater_than_zero_default_timeout_arg)
        time.sleep(greater_than_zero_default_timeout_arg * 0.9)
        assert not timer.is_expired()
        time.sleep(greater_than_zero_default_timeout_arg)
        assert timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case3b
    ####################################################################
    def test_timer_case3b(
        self, greater_than_zero_default_timeout_arg: IntFloat
    ) -> None:
        """Test timer case3b.

        Args:
            greater_than_zero_default_timeout_arg: pytest fixture for
                                                     timeout seconds

        """
        print("mainline entered")
        timer = Timer(
            timeout=None, default_timeout=greater_than_zero_default_timeout_arg
        )
        time.sleep(greater_than_zero_default_timeout_arg * 0.9)
        assert not timer.is_expired()
        time.sleep(greater_than_zero_default_timeout_arg)
        assert timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case4a
    ####################################################################
    def test_timer_case4a(self, zero_or_less_timeout_arg: IntFloat) -> None:
        """Test timer case4a.

        Args:
            zero_or_less_timeout_arg: pytest fixture for timeout seconds

        """
        print("mainline entered")
        timer = Timer(timeout=zero_or_less_timeout_arg)
        time.sleep(abs(zero_or_less_timeout_arg * 0.9))
        assert not timer.is_expired()
        time.sleep(abs(zero_or_less_timeout_arg))
        assert not timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case4b
    ####################################################################
    def test_timer_case4b(self, zero_or_less_timeout_arg: IntFloat) -> None:
        """Test timer case4b.

        Args:
            zero_or_less_timeout_arg: pytest fixture for timeout seconds

        """
        print("mainline entered")
        timer = Timer(timeout=zero_or_less_timeout_arg, default_timeout=None)
        time.sleep(abs(zero_or_less_timeout_arg * 0.9))
        assert not timer.is_expired()
        time.sleep(abs(zero_or_less_timeout_arg))
        assert not timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case5
    ####################################################################
    def test_timer_case5(
        self,
        zero_or_less_timeout_arg: IntFloat,
        zero_or_less_default_timeout_arg: IntFloat,
    ) -> None:
        """Test timer case5.

        Args:
            zero_or_less_timeout_arg: pytest fixture for timeout seconds
            zero_or_less_default_timeout_arg: pytest fixture for timeout
                                                seconds

        """
        print("mainline entered")
        timer = Timer(
            timeout=zero_or_less_timeout_arg,
            default_timeout=zero_or_less_default_timeout_arg,
        )
        time.sleep(abs(zero_or_less_timeout_arg * 0.9))
        assert not timer.is_expired()
        time.sleep(abs(zero_or_less_timeout_arg))
        assert not timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case6
    ####################################################################
    def test_timer_case6(
        self,
        zero_or_less_timeout_arg: IntFloat,
        greater_than_zero_default_timeout_arg: IntFloat,
    ) -> None:
        """Test timer case6.

        Args:
            zero_or_less_timeout_arg: pytest fixture for timeout seconds
            greater_than_zero_default_timeout_arg: pytest fixture for
                                                     timeout seconds

        """
        print("mainline entered")
        timer = Timer(
            timeout=zero_or_less_timeout_arg,
            default_timeout=greater_than_zero_default_timeout_arg,
        )
        time.sleep(abs(zero_or_less_timeout_arg * 0.9))
        assert not timer.is_expired()
        time.sleep(abs(zero_or_less_timeout_arg))
        assert not timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case7a
    ####################################################################
    def test_timer_case7a(self, greater_than_zero_timeout_arg: IntFloat) -> None:
        """Test timer case7a.

        Args:
            greater_than_zero_timeout_arg: pytest fixture for timeout
                                             seconds

        """
        print("mainline entered")
        timer = Timer(timeout=greater_than_zero_timeout_arg)
        time.sleep(greater_than_zero_timeout_arg * 0.9)
        assert not timer.is_expired()
        time.sleep(greater_than_zero_timeout_arg)
        assert timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case7b
    ####################################################################
    def test_timer_case7b(self, greater_than_zero_timeout_arg: IntFloat) -> None:
        """Test timer case7b.

        Args:
            greater_than_zero_timeout_arg: pytest fixture for timeout
                                             seconds

        """
        print("mainline entered")
        timer = Timer(timeout=greater_than_zero_timeout_arg, default_timeout=None)
        time.sleep(greater_than_zero_timeout_arg * 0.9)
        assert not timer.is_expired()
        time.sleep(greater_than_zero_timeout_arg)
        assert timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case8
    ####################################################################
    def test_timer_case8(
        self,
        greater_than_zero_timeout_arg: IntFloat,
        zero_or_less_default_timeout_arg: IntFloat,
    ) -> None:
        """Test timer case8.

        Args:
            greater_than_zero_timeout_arg: pytest fixture for timeout
                                             seconds
            zero_or_less_default_timeout_arg: pytest fixture for timeout
                                                seconds

        """
        print("mainline entered")
        timer = Timer(
            timeout=greater_than_zero_timeout_arg,
            default_timeout=zero_or_less_default_timeout_arg,
        )
        time.sleep(greater_than_zero_timeout_arg * 0.9)
        assert not timer.is_expired()
        time.sleep(greater_than_zero_timeout_arg)
        assert timer.is_expired()
        print("mainline exiting")

    ####################################################################
    # test_timer_case9
    ####################################################################
    def test_timer_case9(
        self,
        greater_than_zero_timeout_arg: IntFloat,
        greater_than_zero_default_timeout_arg: IntFloat,
    ) -> None:
        """Test timer case9.

        Args:
            greater_than_zero_timeout_arg: pytest fixture for timeout
                                             seconds
            greater_than_zero_default_timeout_arg: pytest fixture for
                                                     timeout seconds
        """
        print("mainline entered")
        timer = Timer(
            timeout=greater_than_zero_timeout_arg,
            default_timeout=greater_than_zero_default_timeout_arg,
        )
        time.sleep(greater_than_zero_timeout_arg * 0.9)
        assert not timer.is_expired()
        time.sleep(greater_than_zero_timeout_arg)
        assert timer.is_expired()
        print("mainline exiting")


########################################################################
# TestTimerBasic class
########################################################################
class TestTimerRemainingTime:
    """Test remaining_time method of Timer."""

    ####################################################################
    # test_timer_remaining_time1
    ####################################################################
    def test_timer_remaining_time1(self, timeout_arg: IntFloat) -> None:
        """Test timer remaining time1.

        Args:
            timeout_arg: number of seconds to use for timer timeout arg

        """
        tolerance_factor = 0.80
        logger.debug("mainline entered")
        stop_watch = StopWatch()
        sleep_time = timeout_arg / 3
        exp_remaining_time1: float = timeout_arg - sleep_time
        exp_remaining_time2: float = timeout_arg - sleep_time * 2
        exp_remaining_time3 = 0.0001

        timer = Timer(timeout=timeout_arg)
        stop_watch.start_clock(clock_iter=1)
        stop_watch.pause(sleep_time, clock_iter=1)

        rem_time = timer.remaining_time()
        assert (
            (exp_remaining_time1 * tolerance_factor)
            <= cast(float, rem_time)
            <= exp_remaining_time1
        )
        assert not timer.is_expired()
        logger.debug(f"after third 1: " f"{exp_remaining_time1=}, {rem_time=}")

        stop_watch.pause(sleep_time * 2, clock_iter=1)

        rem_time = timer.remaining_time()
        assert (
            (exp_remaining_time2 * tolerance_factor)
            <= cast(float, rem_time)
            <= exp_remaining_time2
        )
        assert not timer.is_expired()
        logger.debug(f"after third 2: " f"{exp_remaining_time2=}, {rem_time=}")

        time.sleep(sleep_time + 0.1)

        rem_time = timer.remaining_time()
        assert exp_remaining_time3 == cast(float, rem_time)
        assert timer.is_expired()

        logger.debug(f"after third 3: " f"{exp_remaining_time3=}, {rem_time=}")

        logger.debug(f"{stop_watch.start_time=} " f"{timer.start_time=}")

        logger.debug("mainline exiting")

    ####################################################################
    # test_timer_remaining_time_none
    ####################################################################
    def test_timer_remaining_time_none(self) -> None:
        """Test timer remaining time none2."""
        logger.debug("mainline entered")

        timer = Timer(timeout=None)
        time.sleep(1)
        assert timer.remaining_time() is None
        assert not timer.is_expired()

        time.sleep(1)

        assert timer.remaining_time() is None
        assert not timer.is_expired()

        logger.debug("mainline exiting")
