"""test_timer.py module."""

########################################################################
# Standard Library
########################################################################
import time

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################
from scottbrian_utils.timer import Timer

import logging

logger = logging.getLogger(__name__)


##############################################################################
# Timer test exceptions
###############################################################################
class ErrorTstTimer(Exception):
    """Base class for exception in this module."""
    pass


class InvalidRouteNum(ErrorTstTimer):
    """InvalidRouteNum exception class."""
    pass


class InvalidModeNum(ErrorTstTimer):
    """InvalidModeNum exception class."""
    pass


class BadRequestStyleArg(ErrorTstTimer):
    """BadRequestStyleArg exception class."""
    pass


class IncorrectWhichTimer(ErrorTstTimer):
    """IncorrectWhichTimer exception class."""
    pass


###############################################################################
# ReqTime data class used for shutdown testing
###############################################################################
# @dataclass
# class ReqTime:
#     """ReqTime class contains number of completed requests and last time."""
#     num_reqs: int = 0
#     f_time: float = 0.0
#
#
# ###############################################################################
# # requests_arg fixture
# ###############################################################################
# requests_arg_list = [1, 2, 3]
#
#
# @pytest.fixture(params=requests_arg_list)  # type: ignore
# def requests_arg(request: Any) -> int:
#     """Using different requests.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ###############################################################################
# # seconds_arg fixture
# ###############################################################################
# seconds_arg_list = [0.3, 0.5, 1, 2]
#
#
# @pytest.fixture(params=seconds_arg_list)  # type: ignore
# def seconds_arg(request: Any) -> Union[int, float]:
#     """Using different seconds.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(Union[int, float], request.param)
#
#
# ###############################################################################
# # shutdown_requests_arg fixture
# ###############################################################################
# shutdown_requests_arg_list = [1, 3]
#
#
# @pytest.fixture(params=shutdown_requests_arg_list)  # type: ignore
# def shutdown_requests_arg(request: Any) -> int:
#     """Using different requests.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ###############################################################################
# # f_num_reqs_arg fixture
# ###############################################################################
# f_num_reqs_arg_list = [0, 16, 32]
#
#
# @pytest.fixture(params=f_num_reqs_arg_list)  # type: ignore
# def f1_num_reqs_arg(request: Any) -> int:
#     """Number of requests to make for f1.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# @pytest.fixture(params=f_num_reqs_arg_list)  # type: ignore
# def f2_num_reqs_arg(request: Any) -> int:
#     """Number of requests to make for f2.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# @pytest.fixture(params=f_num_reqs_arg_list)  # type: ignore
# def f3_num_reqs_arg(request: Any) -> int:
#     """Number of requests to make for f3.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# @pytest.fixture(params=f_num_reqs_arg_list)  # type: ignore
# def f4_num_reqs_arg(request: Any) -> int:
#     """Number of requests to make for f4.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# @pytest.fixture(params=f_num_reqs_arg_list)  # type: ignore
# def f5_num_reqs_arg(request: Any) -> int:
#     """Number of requests to make for f5.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ###############################################################################
# # num_shutdown1_funcs_arg fixture
# ###############################################################################
# num_shutdown1_funcs_arg_list = [0, 1, 2, 3, 4]
#
#
# @pytest.fixture(params=num_shutdown1_funcs_arg_list)  # type: ignore
# def num_shutdown1_funcs_arg(request: Any) -> int:
#     """Number of requests to shutdown in first shutdown.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ###############################################################################
# # shutdown_seconds_arg fixture
# ###############################################################################
# shutdown_seconds_arg_list = [0.3, 1, 2]
#
#
# @pytest.fixture(params=shutdown_seconds_arg_list)  # type: ignore
# def shutdown_seconds_arg(request: Any) -> Union[int, float]:
#     """Using different seconds.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(Union[int, float], request.param)


###############################################################################
# shutdown_type_arg fixture
###############################################################################
# shutdown1_type_arg_list = [None,
#                            Timer.TYPE_SHUTDOWN_SOFT,
#                            Timer.TYPE_SHUTDOWN_HARD]
#
#
# @pytest.fixture(params=shutdown1_type_arg_list)  # type: ignore
# def shutdown1_type_arg(request: Any) -> int:
#     """Using different shutdown types.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# shutdown2_type_arg_list = [Timer.TYPE_SHUTDOWN_SOFT,
#                            Timer.TYPE_SHUTDOWN_HARD]


# @pytest.fixture(params=shutdown2_type_arg_list)  # type: ignore
# def shutdown2_type_arg(request: Any) -> int:
#     """Using different shutdown types.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ###############################################################################
# # timeout_arg fixture
# ###############################################################################
# timeout_arg_list = [True, False]
#
#
# @pytest.fixture(params=timeout_arg_list)  # type: ignore
# def timeout1_arg(request: Any) -> bool:
#     """Whether to use timeout.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#
#     """
#     return cast(bool, request.param)
#
#
# @pytest.fixture(params=timeout_arg_list)  # type: ignore
# def timeout2_arg(request: Any) -> bool:
#     """Whether to use timeout.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#
#     """
#     return cast(bool, request.param)
#
#
# ###############################################################################
# # sleep_delay_arg fixture
# ###############################################################################
# sleep_delay_arg_list = [0.3, 1.1]
#
#
# @pytest.fixture(params=sleep_delay_arg_list)  # type: ignore
# def sleep_delay_arg(request: Any) -> float:
#     """Whether to use timeout.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#
#     """
#     return cast(float, request.param)
#
#
# ###############################################################################
# # sleep2_delay_arg fixture
# ###############################################################################
# sleep2_delay_arg_list = [0.3, 1.1]
#
#
# @pytest.fixture(params=sleep2_delay_arg_list)  # type: ignore
# def sleep2_delay_arg(request: Any) -> float:
#     """Whether to use timeout.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#
#     """
#     return cast(float, request.param)
#
#
# ###############################################################################
# # which_throttle_arg fixture
# ###############################################################################
# WT = Enum('WT',
#           'PieTimerDirectShutdown '
#           'PieTimerShutdownFuncs '
#           'NonPieTimer')
#
# which_throttle_arg_list = [WT.PieTimerDirectShutdown,
#                            WT.PieTimerShutdownFuncs,
#                            WT.NonPieTimer]
#
#
# @pytest.fixture(params=which_throttle_arg_list)  # type: ignore
# def which_throttle_arg(request: Any) -> int:
#     """Using different requests.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ###############################################################################
# # mode_arg fixture
# ###############################################################################
# mode_arg_list = [Timer.MODE_ASYNC,
#                  Timer.MODE_SYNC,
#                  Timer.MODE_SYNC_LB,
#                  Timer.MODE_SYNC_EC]
#
#
# @pytest.fixture(params=mode_arg_list)  # type: ignore
# def mode_arg(request: Any) -> int:
#     """Using different modes.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ###############################################################################
# # mode_arg fixture
# ###############################################################################
# lb_threshold_arg_list = [0.1, 1, 1.5, 3]
#
#
# @pytest.fixture(params=lb_threshold_arg_list)  # type: ignore
# def lb_threshold_arg(request: Any) -> Union[int, float]:
#     """Using different lb_threshold values.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(Union[int, float], request.param)
#
#
# ###############################################################################
# # early_count_arg fixture
# ###############################################################################
# early_count_arg_list = [1, 2, 3]
#
#
# @pytest.fixture(params=early_count_arg_list)  # type: ignore
# def early_count_arg(request: Any) -> int:
#     """Using different early_count values.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ###############################################################################
# # send_interval_mult_arg fixture
# ###############################################################################
# send_interval_mult_arg_list = [0.0, 0.3, 0.9, 1.0, 1.1]
#
#
# @pytest.fixture(params=send_interval_mult_arg_list)  # type: ignore
# def send_interval_mult_arg(request: Any) -> float:
#     """Using different send rates.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(float, request.param)
#
#
# ###############################################################################
# # request_style_arg fixture
# ###############################################################################
# request_style_arg_list = [0, 1, 2, 3, 4, 5, 6]
#
#
# @pytest.fixture(params=request_style_arg_list)  # type: ignore
# def request_style_arg(request: Any) -> int:
#     """Using different early_count values.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)


###############################################################################
# TestTimerBasic class to test Timer methods
###############################################################################
# class TestTimerErrors:
#     """TestTimer class."""
#     def test_timer_bad_args(self) -> None:
#         """test_timer using bad arguments."""
#         #######################################################################
#         # bad requests
#         #######################################################################
#         with pytest.raises(IncorrectRequestsSpecified):
#             _ = Timer(requests=0,
#                          seconds=1,
#                          mode=Timer.MODE_ASYNC)
#         with pytest.raises(IncorrectRequestsSpecified):
#             _ = Timer(requests=-1,
#                          seconds=1,
#                          mode=Timer.MODE_ASYNC)
#         with pytest.raises(IncorrectRequestsSpecified):
#             _ = Timer(requests='1',  # type: ignore
#                          seconds=1,
#                          mode=Timer.MODE_ASYNC)
#
#         #######################################################################
#         # bad seconds
#         #######################################################################
#         with pytest.raises(IncorrectSecondsSpecified):
#             _ = Timer(requests=1,
#                          seconds=0,
#                          mode=Timer.MODE_ASYNC)
#         with pytest.raises(IncorrectSecondsSpecified):
#             _ = Timer(requests=1,
#                          seconds=-1,
#                          mode=Timer.MODE_ASYNC)
#         with pytest.raises(IncorrectSecondsSpecified):
#             _ = Timer(requests=1,
#                          seconds='1',  # type: ignore
#                          mode=Timer.MODE_ASYNC)
#
#         #######################################################################
#         # bad mode
#         #######################################################################
#         with pytest.raises(IncorrectModeSpecified):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=-1)
#         with pytest.raises(IncorrectModeSpecified):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=0)
#         with pytest.raises(IncorrectModeSpecified):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_MAX+1)
#         with pytest.raises(IncorrectModeSpecified):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode='1')  # type: ignore
#
#         #######################################################################
#         # bad async_q_size
#         #######################################################################
#         with pytest.raises(IncorrectAsyncQSizeSpecified):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_ASYNC,
#                          async_q_size=-1)
#         with pytest.raises(IncorrectAsyncQSizeSpecified):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_ASYNC,
#                          async_q_size=0)
#         with pytest.raises(IncorrectAsyncQSizeSpecified):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_ASYNC,
#                          async_q_size='1')  # type: ignore
#         with pytest.raises(AsyncQSizeNotAllowed):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC,
#                          async_q_size=256)
#         with pytest.raises(AsyncQSizeNotAllowed):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC_EC,
#                          async_q_size=256,
#                          early_count=3)
#         with pytest.raises(AsyncQSizeNotAllowed):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC_LB,
#                          async_q_size=256,
#                          lb_threshold=3)
#         #######################################################################
#         # bad early_count
#         #######################################################################
#         with pytest.raises(EarlyCountNotAllowed):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_ASYNC,
#                          early_count=0)
#         with pytest.raises(EarlyCountNotAllowed):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC,
#                          early_count=1)
#         with pytest.raises(MissingEarlyCountSpecification):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC_EC)
#         with pytest.raises(EarlyCountNotAllowed):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC_LB,
#                          early_count=1)
#         with pytest.raises(IncorrectEarlyCountSpecified):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC_EC,
#                          early_count=-1)
#         with pytest.raises(IncorrectEarlyCountSpecified):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC_EC,
#                          early_count='1')  # type: ignore
#         #######################################################################
#         # bad lb_threshold
#         #######################################################################
#         with pytest.raises(LbThresholdNotAllowed):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_ASYNC,
#                          lb_threshold=1)
#         with pytest.raises(LbThresholdNotAllowed):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC,
#                          lb_threshold=0)
#         with pytest.raises(LbThresholdNotAllowed):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC_EC,
#                          early_count=3,
#                          lb_threshold=0)
#         with pytest.raises(MissingLbThresholdSpecification):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC_LB)
#         with pytest.raises(IncorrectLbThresholdSpecified):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC_LB,
#                          lb_threshold=-1)
#         with pytest.raises(IncorrectLbThresholdSpecified):
#             _ = Timer(requests=1,
#                          seconds=1,
#                          mode=Timer.MODE_SYNC_LB,
#                          lb_threshold='1')  # type: ignore


###############################################################################
# TestTimerBasic class to test Timer methods
###############################################################################
class TestTimerBasic:
    """Test basic functions of Timer."""

    ###########################################################################
    # test_timer_example1
    ###########################################################################
    def test_timer_example(self) -> None:
        """Test timer example."""
        # create a timer and use in a loop
        print('mainline entered')
        timer = Timer(timeout=3)
        for idx in range(10):
            print(f'idx = {idx}')
            time.sleep(1)
            if timer.is_expired():
                print('timer has expired')
            break
        print('mainline exiting')
